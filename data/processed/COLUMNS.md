# Processed tables: columns

Written by `python -m data.process` from the cache in `data/raw/`. COMP amounts are in whole COMP (wei / 1e18). Addresses are lower-case hex.

## proposals.csv (one row per GovernorBravo proposal)
| Column | Meaning |
|---|---|
| proposal_id | Proposal number (43–393) |
| proposer | Address that created it |
| created_block | Block of the `ProposalCreated` event |
| start_block, start_date | Block where voting opens, and its UTC date |
| end_block, end_date | Block where voting closes, and its UTC date |
| snapshot_block | Block at which voting weights are taken (= start_block, as in `getPriorVotes`) |
| canceled_event, queued_event, executed_event | Whether that event was emitted for the proposal |
| state_onchain | `state(id)` read on-chain at the config's end block |
| for_onchain, against_onchain, abstain_onchain | Tallies read on-chain from `proposals(id)` |
| title | First line of the proposal description |
| against, for, abstain | Tallies summed by us from `VoteCast` events |
| n_voters | Number of `VoteCast` events |
| outcome | Our label: executed, queued, succeeded, defeated or canceled |

## votes.csv (one row per vote)
| Column | Meaning |
|---|---|
| proposal_id | Proposal voted on |
| voter | Voting address |
| support | 0 against, 1 for, 2 abstain |
| votes | Vote weight (COMP) |
| block | Block of the vote |

## delegations.csv (one row per `DelegateChanged` event)
| Column | Meaning |
|---|---|
| block, log_index | Position of the event (orders events within a block) |
| delegator | Address whose tokens are delegated |
| from_delegate, to_delegate | Previous and new delegate (`0x0…0` means none) |

## balances.csv.gz (per proposal: every delegating address with a positive balance)
| Column | Meaning |
|---|---|
| proposal_id, snapshot_block | Proposal and its snapshot block |
| address | Delegating address |
| balance | Its COMP balance at the snapshot, from replaying every `Transfer` |
| delegatee | Its delegate at the snapshot |

## weights.csv.gz (per proposal: every delegate's voting weight)
| Column | Meaning |
|---|---|
| proposal_id, snapshot_block | Proposal and its snapshot block |
| delegate | Delegate address |
| weight | Our one-hop weight: sum of balances delegated to it (the protocol's rule; players are rows with weight > 0) |
| weight_transitive | Weight under the transitive rule with the cycle rule (sensitivity only) |
| weight_onchain | The contract's own checkpoint (`DelegateVotesChanged`) at the snapshot, for validation |

## validation.csv (per proposal)
| Column | Meaning |
|---|---|
| proposal_id, snapshot_block | Proposal and its snapshot block |
| n_players, n_players_onchain | Delegates with positive weight: ours and on-chain |
| total_weight, total_weight_onchain | Total delegated weight: ours and on-chain |
| n_mismatch, max_abs_diff | Delegates whose weight differs from on-chain, and the largest difference |
| n_votes, n_vote_mismatch, max_vote_diff | Votes, votes whose weight differs from our weight, and the largest difference |

## counts.json
Size of `data/raw/` in MiB (`raw_mb`), the number of events of each type, and the UTC dates of the reference blocks and the end block in `config.yaml`.
