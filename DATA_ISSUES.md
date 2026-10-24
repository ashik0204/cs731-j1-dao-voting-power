# Data issues

Every proposal in the window is kept. Nothing was silently dropped.

| # | Issue | Effect | Handling |
|---|---|---|---|
| 1 | No private archive node was available, and `ethereum-rpc.publicnode.com` refuses archive requests without a token. | None on results. | `data/rpc.py` uses `$RPC_URL` if set, otherwise the public archive endpoints `gateway.tenderly.co/public/mainnet` and `rpc.mevblocker.io`. All responses are cached in `data/raw/`. |
| 2 | Proposal 270 has two `ProposalCanceled` events (38 events, 37 canceled proposals). | None: a proposal is canceled once. | Outcome uses a set of canceled ids. On-chain `state(270)` = Canceled. |
| 3 | 37 of 351 proposals were canceled before or during voting. | No decision to analyse. | Kept in `proposals.csv` and in the power-index tables (the snapshot game exists), excluded only from the votes-to-outcome analysis (`results/pivotal_per_proposal.csv`, `analysed = False`). |
| 4 | Governor Alpha proposals 1–42 (before Bravo) and Compound's post-Bravo governor are outside the window. | Scope limit. | Window fixed in `config.yaml` to the Bravo period (blocks 12006099–22000000). Bravo's last proposal is 393, created at block 21725397. |
| 5 | Delegates below half a rounding unit (total weight / 20000, about 78 COMP) round to weight 0 in the integer game. | At most 0.12% of voting weight per proposal (`results/games_r20000.csv: dummy_weight_share`). | These players get index 0. Raising the resolution to 50000 changes any index by at most 0.00016 (`results/resolution_sensitivity.csv`). |

## Validation performed (all passed)

- Our delegate weights (one-hop delegation and balances replayed from every COMP `Transfer`) equal the on-chain checkpoint value from `DelegateVotesChanged` for **every delegate at every one of the 351 snapshots**: 0 mismatches (`data/processed/validation.csv`).
- Each of the 14,396 `VoteCast` weights equals our weight for that voter at the proposal's snapshot: 0 mismatches.
- Our for/against/abstain tallies equal `proposals(id)` read on-chain at the end block (maximum difference 2.3e-10 COMP, float rounding).
- Our outcome labels equal on-chain `state(id)` for all 351 proposals.
- `quorumVotes()` read on-chain = 400,000 COMP, matching `config.yaml`.
