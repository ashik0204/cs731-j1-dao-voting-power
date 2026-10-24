# J1: On-chain governance, measuring voting power concentration

CS731 (Blockchain Technology and Applications), IIT Kanpur. Project group 14: Ashik Stenny and Aarav Oswal.
Presentation: 28 Oct 2026 (slot 14, Group A). Slides go to the shared drive before the presentation.

This file is the build brief for the coding assistant. Build everything described here, in this repo, and keep the README updated as the source of truth for how to reproduce every number.

## 1. Goal

Measure the actual decision-making power of voters in one DAO (Decentralized Autonomous Organization), using delegation-aware power indices over its historical proposals. Compare each voter's effective power with their raw token share, and report how often a small set of addresses decided outcomes.

The core contribution is the power-index computation over the delegation graph, implemented by us. Token share or Gini coefficients alone are not enough.

## 2. Scope

- **Primary DAO:** Compound (Governor Bravo / Governor Alpha on-chain proposals and votes), or Uniswap if Compound data is unavailable. Pick one and fix it in `config.yaml`. **Chosen: Compound GovernorBravo, see section 11.**
- **Optional second DAO:** only after the primary pipeline works end to end and passes tests.
- **Time window:** the proposals that were decided and executed or defeated, using a fixed block range recorded in `config.yaml`.

## 3. Data

Collect, for each proposal:
- proposal id, start block, end block, outcome (passed, defeated, cancelled, queued/executed)
- every vote: voter address, support (for/against/abstain), weight at the snapshot block
- delegation events up to the snapshot block: delegator, from delegatee, to delegatee
- token balances of each address at the snapshot block

**Snapshot rule:** for each proposal, take token balances and delegations at the block when voting opened (the proposal's start block). Record the snapshot block number with the data.

**Data sources, in order of preference:**
1. An archive Ethereum node (Alchemy, Infura, or a local node) with `eth_getLogs` for the governance and token contracts
2. The Graph subgraph for the DAO, if one exists
3. Tally or Compound's public API, only for cross-checking

Cache raw responses under `data/raw/` so the pipeline can be rerun offline. Never commit API keys. Read them from environment variables and document them in the README.

## 4. What must be implemented by us (no library calls)

These are the contribution. Do not use an existing power-index library or a governance analytics package for them.

**a. Delegation resolution.** Given the delegation events up to a block, compute each address's delegatee. Handle chains (A to B to C), self-delegation, and undelegation. Each address's voting weight is the total token balance of addresses delegated to it, with delegation cycles resolved to a defined rule (document the rule).

**b. Players.** Treat each address that holds positive voting weight at the snapshot as one player in the voting game. State explicitly how delegators and delegates are represented (a delegate's weight already includes its delegators, so delegators are not separate players). Write the choice in the README.

**c. Winning rule.** A proposal passes if for-votes exceed against-votes and quorum is met. Model each proposal as a weighted voting game with quota equal to the threshold the protocol requires, and document the quota formula.

**d. Banzhaf index.** For each player i, count the coalitions S of the other players such that S alone loses and S plus i wins (the swings). Normalise so the indices sum to 1. Use dynamic programming over integer weights. Brute-force enumeration over subsets is only acceptable as a test oracle for small instances.

**e. Shapley-Shubik index.** For each player i, the fraction of permutations of all players in which i is the pivotal player (the player whose arrival first makes the running weight meet the quota). Compute this with dynamic programming over weights, not by enumerating n! permutations, for real DAO sizes.

**f. Turning votes into power.** For each proposal, compare the realised outcome with the power indices. Record whether the outcome was decided by a set of addresses whose combined weight was minimal (for example, the smallest set of players that could have changed the result). Report how often a top-k set of addresses was pivotal.

**g. Gap analysis.** For each DAO, compare each address's nominal token share with its Banzhaf and Shapley-Shubik indices. Report the largest gaps and the rank correlation between the two indices.

## 5. Correctness tests (required)

- **Known example:** weights (50, 30, 20) with quota 51. Banzhaf normalised = (0.50, 0.25, 0.25). Shapley-Shubik = (0.6667, 0.1667, 0.1667). Test these to tolerance 1e-9.
- **Dummy player:** a player with zero weight has index 0 under both measures.
- **Symmetry:** two players with equal weight have equal indices.
- **Efficiency (Shapley-Shubik):** indices sum to 1.
- **DP vs brute force:** on random small instances (n <= 12) the dynamic-programming results match brute-force enumeration.
- **Delegation:** unit tests for chains, cycles, self-delegation and undelegation.
- **Snapshot:** a test that balances and delegations at a block are not altered by events after that block.

All tests run with one command and must pass before any result is reported.

## 6. Deliverables

1. Repo that builds and runs from a clean checkout (`README` lists the exact commands).
2. `data/` pipeline that writes raw, cached data and processed tables (CSV).
3. `power/` package with the delegation resolver and the two indices, plus tests.
4. `analysis/` scripts that produce every figure and table in the report, written to `results/`.
5. Dependency justification (half a page, `DEPENDENCIES.md`): list each external package, what it does, and what we implemented ourselves. Permitted: web3 client, HTTP, DataFrame and plotting libraries, pytest. Not permitted: any power-index or voting-power library.
6. Slides (exported as PDF) for the 28 Oct presentation, in `slides/`.

## 7. Presentation outline (30 to 35 minutes)

1. Problem: nominal vs effective decentralisation in token-weighted DAO voting.
2. Background: weighted voting games, Banzhaf and Shapley-Shubik indices, delegation.
3. What is done: our data pipeline, delegation resolution, index implementations, tests.
4. Results: the Banzhaf vs Shapley-Shubik disagreement, the nominal vs effective gap, how often a few addresses were pivotal.
5. Limitations: snapshot choices, delegation cycles, missing data, model assumption that voters are not strategic.
6. Future directions.

Reference reading: Fritsch, Müller and Wattenhofer, "Analyzing Voting Power in Decentralized Governance" (arXiv 2208.01636). Also Messias et al., "Understanding Blockchain Governance" (arXiv 2304.02625).

## 8. Repo layout

```
config.yaml          DAO, contract addresses, block range, RPC env var name
data/raw/            cached raw responses (not committed if large)
data/processed/      CSVs: proposals, votes, delegations, balances
power/
  delegation.py      delegation resolution
  banzhaf.py         Banzhaf index (DP)
  shapley.py         Shapley-Shubik index (DP)
  gap.py             nominal vs effective comparison
tests/               pytest, including the known examples above
analysis/            scripts producing results/ tables and figures
results/             final tables and figures used in the slides
slides/              presentation source and exported PDF
DEPENDENCIES.md      justification of every external dependency
README.md            this file, kept up to date
```

## 9. Working rules for the coding assistant

- Build step by step, and run the tests after each module.
- Do not change the design in this file without writing the change here first and stating why.
- Do not invent numbers. Every reported number must come from a script in `analysis/` that can be rerun.
- If a data source is unavailable or a block is missing, record it in `DATA_ISSUES.md` and continue. Do not silently drop proposals.
- Keep the code readable enough to explain on slides. Prefer short functions with docstrings that state the formula being computed.
- Report negative or partial results honestly. The course grades unsupported claims down.

## 10. Reproduce

Python 3.13. From a clean checkout:

```
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
pytest                              # 276 tests, ~2 s; must pass before results are reported

# optional: your own archive node. If unset, public archive endpoints are used.
export RPC_URL=...                  # never committed

python -m data.fetch                # ~1 h from scratch: data/raw/ (175 MB of gzip JSON logs + eth_call cache)
python -m data.process              # ~1 min: data/processed/*.csv(.gz) and validation.csv
python -m analysis.compute_indices  # indices for all 351 games; done automatically by run_all if missing
python -m analysis.run_all          # results/: tables, figures, summary.json
cd slides && pdflatex slides.tex && pdflatex slides.tex   # slides/slides.pdf
```

`data.fetch` is restartable: each 500k-block chunk is cached once complete. `data.process` and everything after run offline from the cache. Run commands from the repo root (they read `config.yaml`).

## 11. Design decisions and changes to this brief

Each change below was made for the stated reason. Nothing else in sections 1–9 changed.

1. **DAO and window.** Compound GovernorBravo (proxy `0xc0Da02939E1441F497fd74F78cE7Decb17B66529`), COMP token `0xc00e…6888`, proposals 43–393 (all Bravo proposals), block window 12006099–22000000. Governor Alpha (1–42) and Compound's newer governor are out of scope. Fixed in `config.yaml`.
2. **Snapshot block = proposal `startBlock`**, including events in that block. This is exactly what Bravo's `getPriorVotes(voter, startBlock)` uses, so our weights can be checked against every vote (see `DATA_ISSUES.md`: 0 mismatches).
3. **Delegation rule (4a).** COMP delegation is *one-hop*: if A→B and B→C, A's tokens count for B and B's own tokens for C. Tokens of an address that never delegated (or undelegated to `0x0`) count for nobody, including itself. This rule is used for all results because it is what the protocol counts. We also implement a *transitive* rule for sensitivity: follow the chain to an address that is self-delegated or not delegating. **Cycle rule:** addresses on a cycle are treated as self-delegated, and a chain entering a cycle stops at the first cycle address it meets. Switching to the transitive rule moves at most 5.3% of voting weight in any proposal (`results/transitive_vs_onehop.csv`).
4. **Players (4b).** One player per address with positive (one-hop) voting weight at the snapshot: a median of 4,912 per proposal. A delegate's weight already includes its delegators, so delegators are not players. Weights are reconstructed by us from all 2.33M COMP `Transfer` and 16k `DelegateChanged` events.
5. **Quota (4c).** With every player voting for or against, the for-coalition S passes iff w(S) > w(N∖S) and w(S) ≥ Q (Q = 400,000 COMP), i.e. **q = max(⌊W/2⌋ + 1, ⌈Q/u⌉)** in integer units. Delegated weight is 1.76M–3.13M COMP, so the majority term always binds in this game (`quorum_binds = 0` proposals). Quorum matters in the realised-vote analysis (4f), where turnout is low.
6. **Integer weights.** Weights are rounded to units u = W / 20000 (`config.yaml: power.resolution`). Players below u/2 become dummies, holding at most 0.12% of weight. Raising the resolution to 50000 changes any index by at most 0.00016. Null players are removed before the DP, which does not change the other players' Banzhaf (normalised) or Shapley-Shubik values.
7. **DP algorithms (4d, 4e).** Banzhaf uses DP over the subset-weight distribution; Shapley-Shubik uses DP over (coalition size, weight) with a normalised, convex-combination recurrence that cannot overflow. Leave-one-out uses divide and conquer over distinct weights (additions only, no unstable deconvolution). Formulas are in the module docstrings.
8. **Known-example correction (section 5).** For [51; 50, 30, 20] the normalised Banzhaf index is **(0.6, 0.2, 0.2)**, not (0.50, 0.25, 0.25). The winning coalitions are {1,2}, {1,3} and {1,2,3}, so player 1 has 3 swings and players 2 and 3 have one each. The raw Banzhaf values are (0.75, 0.25, 0.25). Brute-force enumeration agrees. The test checks the correct values. Shapley-Shubik (2/3, 1/6, 1/6) is as stated.
9. **Rank correlation (4g).** In a weighted voting game both indices are monotone in weight (a heavier player is at least as desirable), so their Spearman correlation is 1 up to ties. We report it (it is 1.000 for every proposal) and explain this. To measure the real disagreement we add the **total-variation distance** ½Σ|β_i − φ_i| between the index vectors, and the same distance from token share.
10. **Votes to power (4f).** A *flip set* is a set of players who, changing only their own votes, reverse the result. For a passed proposal, for-voters switch to against and non-voters/abstainers join against. For a defeated one, against-voters switch to for and non-voters/abstainers join for. The quorum rule is applied. We compute the smallest flip set exactly (greedy, or a top-j/top-(k−j) split for defeated proposals; checked against brute force in tests), and whether the top-k delegates by weight form a flip set. Non-voting delegates are included because they could have voted. 37 canceled proposals are excluded from this part only.
11. **No `web3` package.** JSON-RPC is done with `requests` plus our own ABI decoding (`data/abi.py`). This is permitted by section 6 and smaller.

## 12. Results (all from `python -m analysis.run_all`; numbers in `results/summary.json`)

- **Data:** 351 proposals (281 executed, 33 defeated, 37 canceled) and 14,396 votes. Reconstructed weights match the chain exactly (see `DATA_ISSUES.md`).
- **Concentration:** the median largest delegate holds 13.1% of voting weight but 14.9% Banzhaf and 14.3% Shapley-Shubik power. The median top-5 hold 38.2% of weight, 39.6% Banzhaf and 40.6% Shapley-Shubik. The median Nakamoto coefficient (fewest players with more than half) is 10 by weight and 9 by Shapley-Shubik. Of 4,912 players, a median of 76 are non-dummies at our resolution.
- **Nominal vs effective gap:** the one or two largest delegates are amplified (power/share about 1.1), and almost everyone else is compressed (about 0.96). The largest single gap is +4.8 points (Banzhaf) and +2.2 points (Shapley-Shubik) for the top delegate. Tables: `gap_top.csv`, `address_power.csv`. Figures: `fig_gap_scatter.png`, `fig_top10_delegates.png`.
- **Banzhaf vs Shapley-Shubik:** identical rankings (Spearman 1.000, as the theory predicts). Their distributions differ by a total-variation distance of median 0.015 (max 0.026). Banzhaf gives the top delegate more than Shapley-Shubik does after proposal ~225 (`fig_distribution_distance.png`, `fig_top1_power.png`).
- **Votes to outcomes:** of 314 decided proposals, a single address could have reversed 118 (median minimal flip set: 2 addresses; never more than 5). This includes 28 of 33 defeated proposals, mostly quorum failures that one large non-voting delegate could have rescued. The top 1/3/5/10 delegates could alone have reversed 26% / 73% / 97% / 100% of outcomes (`topk_pivotal.csv`, `fig_topk_pivotal.png`, `fig_min_flip_size.png`). Median turnout was 25.5% of delegated weight.
- **Robustness:** integer resolution (max index change 0.00016 from 20000 to 50000) and transitive delegation (at most 5.3% of weight moves).

**Limitations:** single snapshot rule; one-hop delegation, as in the protocol; voters modelled as non-strategic and all-voting in the index game; abstention not modelled in the indices; addresses are not mapped to real-world entities (one entity may control several addresses, which would understate concentration).
