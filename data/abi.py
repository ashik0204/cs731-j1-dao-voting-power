"""Event signatures and the small amount of ABI decoding we need."""
from eth_hash.auto import keccak

SIG = {
    # GovernorBravo
    "ProposalCreated": "ProposalCreated(uint256,address,address[],uint256[],string[],bytes[],uint256,uint256,string)",
    "VoteCast": "VoteCast(address,uint256,uint8,uint256,string)",
    "ProposalCanceled": "ProposalCanceled(uint256)",
    "ProposalQueued": "ProposalQueued(uint256,uint256)",
    "ProposalExecuted": "ProposalExecuted(uint256)",
    # COMP token
    "Transfer": "Transfer(address,address,uint256)",
    "DelegateChanged": "DelegateChanged(address,address,address)",
    "DelegateVotesChanged": "DelegateVotesChanged(address,uint256,uint256)",
}


def topic(name):
    return "0x" + keccak(SIG[name].encode()).hex()


def selector(fn):
    return "0x" + keccak(fn.encode()).hex()[:8]


def word(n):
    return f"{n:064x}"


def words(data):
    """Split ABI-encoded data into 32-byte words (as ints)."""
    h = data[2:]
    return [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]


def addr_topic(t):
    return "0x" + t[-40:]


def addr_word(w):
    return "0x" + f"{w:064x}"[-40:]


def dyn_string(data, offset_word):
    """Decode a dynamic `string` whose offset is stored in word `offset_word`."""
    h = data[2:]
    off = int(h[offset_word * 64:(offset_word + 1) * 64], 16) * 2
    n = int(h[off:off + 64], 16)
    return bytes.fromhex(h[off + 64:off + 64 + 2 * n]).decode("utf-8", errors="replace")
