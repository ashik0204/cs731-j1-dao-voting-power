# Dependency justification

All external packages are generic infrastructure (HTTP, hashing, arrays, tables, plots, tests).
No power-index, voting-power, game-theory or governance-analytics package is used.

| Package | What it does for us | Why not write it ourselves |
|---|---|---|
| `requests` | HTTP POSTs for JSON-RPC (`eth_getLogs`, `eth_call`) in `data/rpc.py` | Plain HTTP client. We use it instead of `web3` to keep the dependency surface small: our JSON-RPC client, log pagination, retry/endpoint rotation, cache, and ABI decoding (`data/abi.py`) are our own. |
| `eth-hash[pycryptodome]` | Keccak-256, to compute event topics and function selectors from their signatures | A cryptographic primitive. Hand-rolling a hash is error-prone and not part of the contribution. |
| `numpy` | Array arithmetic in the DP loops (`power/banzhaf.py`, `power/shapley.py`) | Vectorised shifts and additions of probability arrays. The recurrences, truncation at the quota, and leave-one-out scheme are ours. |
| `pandas` | CSV I/O, joins and group-bys in `data/process.py` and `analysis/` | DataFrame library (permitted). Rank correlation is our own (`power/gap.py: ranks, spearman`), not `pandas.corr` or `scipy`. |
| `matplotlib` | Figures in `results/` | Plotting library (permitted). |
| `PyYAML` | Reads `config.yaml` | Config parsing only. |
| `pytest` | Test runner | Permitted. |

## What we implemented ourselves

- **Delegation resolution and snapshot replay** (`power/delegation.py`): current delegatee from `DelegateChanged` events up to a block, undelegation, one-hop (Compound) and transitive resolution with the documented cycle rule, balances from replaying every COMP `Transfer`, and a single-pass replay over all snapshot blocks.
- **Weighted voting game** (`power/game.py`): Compound's quota rule, integer rounding of weights, and divide-and-conquer leave-one-out over distinct weights.
- **Banzhaf index** (`power/banzhaf.py`): DP over integer weights (subset-weight distribution).
- **Shapley-Shubik index** (`power/shapley.py`): DP over (coalition size, weight) with a normalised, overflow-free recurrence.
- **Brute-force oracles** (`power/bruteforce.py`): subset and permutation enumeration, used only in tests.
- **Outcome analysis** (`power/pivotal.py`): minimal flip set and top-k pivotality.
- **Gap analysis and Spearman correlation** (`power/gap.py`).
- **Data pipeline** (`data/`): log fetching with adaptive range splitting, caching, ABI decoding, and cross-checks against on-chain state.

No external data products (Tally, subgraphs, Dune) are used for any reported number.
