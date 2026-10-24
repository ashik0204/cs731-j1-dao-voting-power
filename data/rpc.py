"""Minimal JSON-RPC client with an on-disk cache for eth_getLogs and eth_call.

Every response is cached under data/raw/ so the pipeline can be rerun offline.
"""
import gzip
import json
import os
import time
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parent / "raw"


class RPC:
    def __init__(self, urls, max_range=100_000):
        self.urls = list(urls)
        self.max_range = max_range
        self.session = requests.Session()
        self._id = 0

    def call(self, method, params, retries=6):
        """Send one JSON-RPC request, rotating over endpoints on failure."""
        last = None
        for attempt in range(retries):
            url = self.urls[attempt % len(self.urls)]
            self._id += 1
            try:
                r = self.session.post(url, json={"jsonrpc": "2.0", "id": self._id,
                                                 "method": method, "params": params}, timeout=120)
                d = r.json()
            except (requests.RequestException, ValueError) as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
                continue
            if "error" in d:
                last = RuntimeError(f"{url}: {d['error']}")
                if _is_range_error(d["error"]):
                    raise RangeTooLarge(str(d["error"]))
                time.sleep(1.5 * (attempt + 1))
                continue
            return d["result"]
        raise RuntimeError(f"{method} failed after {retries} attempts: {last}")

    def get_logs(self, address, topics, start, end):
        """Fetch logs in [start, end], splitting ranges the endpoint refuses."""
        out, lo = [], start
        step = self.max_range
        while lo <= end:
            hi = min(end, lo + step - 1)
            try:
                logs = self.call("eth_getLogs", [{"address": address, "topics": topics,
                                                  "fromBlock": hex(lo), "toBlock": hex(hi)}])
            except RangeTooLarge:
                step = max(1, step // 4)
                continue
            out.extend(_compact(l) for l in logs)
            lo = hi + 1
            if len(logs) < 2000:
                step = min(self.max_range, step * 2)
        return out


class RangeTooLarge(Exception):
    pass


def _is_range_error(err):
    msg = json.dumps(err).lower()
    return any(s in msg for s in ("range", "too many", "limit", "10000 results", "query returned more"))


def _compact(log):
    """Keep only the fields we use, to keep the cache small."""
    return {"block": int(log["blockNumber"], 16), "logIndex": int(log["logIndex"], 16),
            "tx": log["transactionHash"], "topics": log["topics"], "data": log["data"]}


def endpoints():
    """RPC endpoints: $RPC_URL first (if set), then the public fallbacks."""
    urls = []
    if os.environ.get("RPC_URL"):
        urls.append(os.environ["RPC_URL"])
    urls += ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io"]
    return urls


def cached_logs(rpc, name, address, topics, start, end, chunk=500_000):
    """Fetch logs in fixed chunks of `chunk` blocks, caching each chunk as gzip JSON.

    Chunk boundaries are aligned to multiples of `chunk` so reruns with a later
    end block reuse every complete chunk.
    """
    d = RAW / name
    d.mkdir(parents=True, exist_ok=True)
    out = []
    lo = (start // chunk) * chunk
    while lo <= end:
        a, b = max(lo, start), min(lo + chunk - 1, end)
        path = d / f"{a}_{b}.json.gz"
        if path.exists():
            with gzip.open(path, "rt") as f:
                logs = json.load(f)
        else:
            logs = rpc.get_logs(address, topics, a, b)
            tmp = path.with_suffix(".tmp")
            with gzip.open(tmp, "wt") as f:
                json.dump(logs, f)
            tmp.rename(path)
            print(f"  {name}: blocks {a}-{b}: {len(logs)} logs", flush=True)
        out.extend(logs)
        lo += chunk
    return out


def cached_call(rpc, name, to, data, block):
    """eth_call at a historical block, cached in one JSON file per `name`."""
    path = RAW / f"{name}.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    key = f"{to}:{data}:{block}"
    if key not in cache:
        cache[key] = rpc.call("eth_call", [{"to": to, "data": data}, hex(block)])
        path.write_text(json.dumps(cache))
    return cache[key]
