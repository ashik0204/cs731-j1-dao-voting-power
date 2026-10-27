"""Produce every table and figure in results/ from data/processed/.

    python -m analysis.run_all

Every number in the report and slides comes from a file written here.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from analysis.compute_indices import compute
from power.gap import spearman, game_indices
from power.pivotal import min_flip_set, set_flips, passed
from analysis.beyond import participation_games, nakamoto, voters_to_half, gini, fritsch_power

CONFIG = yaml.safe_load(open("config.yaml"))
RES = Path("results")
PROC = Path("data/processed")
Q = CONFIG["governance"]["quorum_votes"]
TOPK = CONFIG["power"]["top_k"]

# Validated categorical slots 1-3 (dataviz reference palette, light surface).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
    "axes.titlesize": 12, "axes.titleweight": "bold", "legend.frameon": False,
    "lines.linewidth": 2, "figure.dpi": 150, "axes.axisbelow": True,
})

SUMMARY = {}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(RES / name)
    plt.close(fig)


def short(a):
    return a[:6] + "…" + a[-4:]


# ---------------------------------------------------------------- data checks
def data_summary(props):
    val = pd.read_csv(PROC / "validation.csv")
    counts = json.loads((PROC / "counts.json").read_text())
    SUMMARY.update({"raw_mb": counts["raw_mb"], "events": counts["events"],
                    "first_start_date": props.start_date.min(), "last_start_date": props.start_date.max(),
                    "fritsch_cutoff_date": counts["reference_dates"]["fritsch_cutoff"],
                    "end_block_date": counts["end_block_date"],
                    "outcome_state_mismatches": int((props.outcome.str.capitalize() != props.state_onchain).sum())})
    SUMMARY["proposals_total"] = len(props)
    SUMMARY["outcomes"] = props.outcome.value_counts().to_dict()
    SUMMARY["onchain_states"] = props.state_onchain.value_counts().to_dict()
    SUMMARY["weights_match_onchain_all_proposals"] = bool((val.n_mismatch == 0).all())
    SUMMARY["delegate_weight_mismatches"] = int(val.n_mismatch.sum())
    SUMMARY["vote_weight_mismatches"] = int(val.n_vote_mismatch.sum())
    SUMMARY["votes_total"] = int(val.n_votes.sum())
    tally_diff = (props[["for", "against", "abstain"]].values -
                  props[["for_onchain", "against_onchain", "abstain_onchain"]].values)
    SUMMARY["max_tally_diff_vs_onchain_COMP"] = float(np.nanmax(np.abs(tally_diff)))
    val.to_csv(RES / "validation_per_proposal.csv", index=False)


def transitive_check():
    w = pd.read_csv(PROC / "weights.csv.gz")
    d = w.assign(diff=(w.weight - w.weight_transitive).abs()).groupby("proposal_id").agg(
        weight_moved=("diff", "sum"), total=("weight", "sum"))
    d["weight_moved_share"] = d.weight_moved / 2 / d.total
    d.to_csv(RES / "transitive_vs_onehop.csv")
    SUMMARY["transitive_proposals_affected"] = int((d.weight_moved > 1e-6).sum())
    SUMMARY["transitive_max_weight_moved_share"] = float(d.weight_moved_share.max())


# ---------------------------------------------------------------- (g) gap analysis
def gap_analysis(ind, games, props):
    ind = ind.merge(props[["proposal_id"]], on="proposal_id")
    n_prop = ind.proposal_id.nunique()

    per = []
    for pid, g in ind.groupby("proposal_id"):
        live = g[g.int_weight > 0]
        ss_sorted = np.sort(g.shapley.values)[::-1]
        per.append({
            "proposal_id": pid,
            "spearman_banzhaf_shapley": spearman(live.banzhaf, live.shapley),
            "spearman_share_banzhaf": spearman(live.share, live.banzhaf),
            "spearman_share_shapley": spearman(live.share, live.shapley),
            "top1_share": g.share.max(), "top1_banzhaf": g.banzhaf.max(), "top1_shapley": g.shapley.max(),
            "top5_share": np.sort(g.share)[::-1][:5].sum(),
            "top5_banzhaf": np.sort(g.banzhaf)[::-1][:5].sum(),
            "top5_shapley": ss_sorted[:5].sum(),
            "nakamoto_share": int(np.searchsorted(np.cumsum(np.sort(g.share)[::-1]), 0.5, side="right") + 1),
            "nakamoto_shapley": int(np.searchsorted(np.cumsum(ss_sorted), 0.5, side="right") + 1),
            # Total-variation distance 0.5 * sum |x - y| between two distributions over players.
            "tv_banzhaf_shapley": 0.5 * (g.banzhaf - g.shapley).abs().sum(),
            "tv_share_banzhaf": 0.5 * (g.banzhaf - g.share).abs().sum(),
            "tv_share_shapley": 0.5 * (g.shapley - g.share).abs().sum(),
            "max_abs_diff_banzhaf_shapley": (g.banzhaf - g.shapley).abs().max(),
            "max_abs_gap_banzhaf": (g.banzhaf - g.share).abs().max(),
            "max_abs_gap_shapley": (g.shapley - g.share).abs().max(),
        })
    per = pd.DataFrame(per).merge(games, on="proposal_id").merge(
        props[["proposal_id", "snapshot_block", "start_date"]], on="proposal_id")
    per.to_csv(RES / "per_proposal_power.csv", index=False)

    # Per address, averaged over all analysed proposals (absent = 0).
    agg = ind.groupby("address")[["share", "banzhaf", "shapley"]].sum() / n_prop
    agg["n_proposals_as_player"] = ind.groupby("address").size()
    agg["gap_banzhaf"] = agg.banzhaf - agg.share
    agg["gap_shapley"] = agg.shapley - agg.share
    agg = agg.sort_values("share", ascending=False)
    agg.to_csv(RES / "address_power.csv")
    top = pd.concat([agg.nlargest(10, "gap_banzhaf").assign(kind="largest positive Banzhaf gap"),
                     agg.nsmallest(10, "gap_banzhaf").assign(kind="largest negative Banzhaf gap"),
                     agg.nlargest(10, "gap_shapley").assign(kind="largest positive Shapley gap"),
                     agg.nsmallest(10, "gap_shapley").assign(kind="largest negative Shapley gap")])
    top.to_csv(RES / "gap_top.csv")
    agg.head(15).to_csv(RES / "top15_addresses.csv")

    # Power per unit of token share, for addresses well above the rounding unit
    # (the population of fig_gap_scatter.png): the two largest vs everyone else.
    big = agg[agg.share >= 4 / CONFIG["power"]["resolution"]]
    ratio = pd.DataFrame({"banzhaf_per_share": big.banzhaf / big.share,
                          "shapley_per_share": big.shapley / big.share, "share": big.share})
    ratio.to_csv(RES / "power_per_share.csv")
    top2, rest = ratio.iloc[:2], ratio.iloc[2:]
    SUMMARY.update({
        "ratio_top2_min": float(top2[["banzhaf_per_share", "shapley_per_share"]].min().min()),
        "ratio_top2_max": float(top2[["banzhaf_per_share", "shapley_per_share"]].max().max()),
        "ratio_rest_median_banzhaf": float(rest.banzhaf_per_share.median()),
        "ratio_rest_median_shapley": float(rest.shapley_per_share.median()),
        "ratio_rest_below_one_share": float((rest.banzhaf_per_share < 1).mean()),
        "ratio_rest_n": len(rest),
    })

    # From which proposal on does Banzhaf give the top delegate clearly more than
    # Shapley-Shubik (by at least 0.5 percentage points in every later proposal)?
    gap = per.sort_values("proposal_id").set_index("proposal_id")
    gap = gap.top1_banzhaf - gap.top1_shapley
    clear = gap >= 0.005
    tail_ok = clear[::-1].cummin()[::-1]
    first = int(tail_ok[tail_ok].index.min())
    SUMMARY.update({"bz_over_ss_from_proposal": first,
                    "bz_over_ss_from_date": str(props.set_index("proposal_id").start_date[first]),
                    "bz_over_ss_min_gap_after": float(gap[gap.index >= first].min()),
                    "bz_over_ss_max_gap_before": float(gap[gap.index < first].max())})

    s = per.spearman_banzhaf_shapley
    SUMMARY.update({
        "proposals_analysed": n_prop,
        "players_median": float(per.n_players.median()), "nondummy_players_median": float(per.n_live.median()),
        "quorum_binds_proposals": int(per.quorum_binds.sum()),
        "dummy_weight_share_max": float(per.dummy_weight_share.max()),
        "spearman_bz_ss_median": float(s.median()), "spearman_bz_ss_min": float(s.min()),
        "spearman_bz_ss_max": float(s.max()),
        "spearman_bz_ss_pooled_address_avg": spearman(agg.banzhaf, agg.shapley),
        "spearman_share_banzhaf_median": float(per.spearman_share_banzhaf.median()),
        "tv_banzhaf_shapley_median": float(per.tv_banzhaf_shapley.median()),
        "tv_banzhaf_shapley_max": float(per.tv_banzhaf_shapley.max()),
        "tv_share_banzhaf_median": float(per.tv_share_banzhaf.median()),
        "tv_share_shapley_median": float(per.tv_share_shapley.median()),
        "max_abs_diff_banzhaf_shapley": float(per.max_abs_diff_banzhaf_shapley.max()),
        "top1_banzhaf_exceeds_share_share": float((per.top1_banzhaf > per.top1_share).mean()),
        "top1_shapley_exceeds_share_share": float((per.top1_shapley > per.top1_share).mean()),
        "top1_share_median": float(per.top1_share.median()),
        "top1_banzhaf_median": float(per.top1_banzhaf.median()),
        "top1_shapley_median": float(per.top1_shapley.median()),
        "top5_share_median": float(per.top5_share.median()),
        "top5_banzhaf_median": float(per.top5_banzhaf.median()),
        "top5_shapley_median": float(per.top5_shapley.median()),
        "nakamoto_share_median": float(per.nakamoto_share.median()),
        "nakamoto_shapley_median": float(per.nakamoto_shapley.median()),
        "max_abs_gap_banzhaf": float(per.max_abs_gap_banzhaf.max()),
        "max_abs_gap_shapley": float(per.max_abs_gap_shapley.max()),
    })
    return per, agg


# ---------------------------------------------------------------- (f) votes -> outcomes
def pivotal_analysis(props):
    votes = pd.read_csv(PROC / "votes.csv")
    w = pd.read_csv(PROC / "weights.csv.gz")
    w = w[w.weight > 0]
    rows = []
    for _, p in props.iterrows():
        if p.outcome == "canceled":
            rows.append({"proposal_id": p.proposal_id, "outcome": p.outcome, "analysed": False})
            continue
        side = {0: "against", 1: "for", 2: "none"}
        v = votes[votes.proposal_id == p.proposal_id]
        vote_side = dict(zip(v.voter, v.support.map(side)))
        wp = w[w.proposal_id == p.proposal_id].sort_values("weight", ascending=False)
        players = [(a, x, vote_side.get(a, "none")) for a, x in zip(wp.delegate, wp.weight)]
        F, A = p["for"], p["against"]
        flip = min_flip_set(players, F, A, Q)
        top = list(wp.delegate)
        r = {"proposal_id": p.proposal_id, "outcome": p.outcome, "analysed": True,
             "passed": passed(F, A, Q), "for": F, "against": A,
             "turnout_share": (F + A + p.abstain) / wp.weight.sum(),
             "min_flip_size": len(flip) if flip else None,
             "min_flip_weight_share": wp.set_index("delegate").weight.loc[flip].sum() / wp.weight.sum() if flip else None,
             "min_flip_within_top10": bool(flip) and set(flip) <= set(top[:10])}
        for k in TOPK:
            r[f"top{k}_flips"] = set_flips(players, F, A, Q, set(top[:k]))
        rows.append(r)
    df = pd.DataFrame(rows)
    df = df.merge(props[["proposal_id", "snapshot_block", "start_date"]], on="proposal_id")
    df.to_csv(RES / "pivotal_per_proposal.csv", index=False)
    a = df[df.analysed]
    summ = pd.DataFrame({"k": TOPK, "share_of_decided_proposals_flippable_by_topk":
                         [a[f"top{k}_flips"].mean() for k in TOPK],
                         "count": [int(a[f"top{k}_flips"].sum()) for k in TOPK],
                         "n_decided": len(a)})
    summ.to_csv(RES / "topk_pivotal.csv", index=False)
    SUMMARY.update({
        "decided_proposals": len(a), "canceled_excluded": int((~df.analysed).sum()),
        "passed": int(a.passed.sum()), "defeated": int((~a.passed.astype(bool)).sum()),
        "min_flip_size_median": float(a.min_flip_size.median()),
        "min_flip_size_counts": {int(k): int(v) for k, v in a.min_flip_size.value_counts().sort_index().items()},
        "min_flip_within_top10_share": float(a.min_flip_within_top10.mean()),
        "topk_flip_share": {int(k): float(a[f"top{k}_flips"].mean()) for k in TOPK},
        "turnout_share_median": float(a.turnout_share.median()),
    })
    return df


# ---------------------------------------------------------------- sensitivity
def resolution_sensitivity(props):
    """Indices at several integer resolutions on a sample of proposals."""
    ids = list(props.proposal_id.iloc[::25])
    res = CONFIG["power"]["sensitivity_resolutions"]
    w = pd.read_csv(PROC / "weights.csv.gz")
    w = w[w.weight > 0]
    rows = []
    for pid in ids:
        wp = w[w.proposal_id == pid]
        weights = dict(zip(wp.delegate, wp.weight))
        ref = game_indices(weights, Q, max(res)).set_index("address")
        for r in res:
            df = ref if r == max(res) else game_indices(weights, Q, r).set_index("address")
            rows.append({"proposal_id": pid, "resolution": r,
                         "max_abs_diff_banzhaf_vs_max_res": float((df.banzhaf - ref.banzhaf).abs().max()),
                         "max_abs_diff_shapley_vs_max_res": float((df.shapley - ref.shapley).abs().max()),
                         "n_live": int((df.int_weight > 0).sum())})
    d = pd.DataFrame(rows)
    d.to_csv(RES / "resolution_sensitivity.csv", index=False)
    main = d[d.resolution == CONFIG["power"]["resolution"]]
    SUMMARY["resolution_sensitivity_max_diff_banzhaf"] = float(main.max_abs_diff_banzhaf_vs_max_res.max())
    SUMMARY["resolution_sensitivity_max_diff_shapley"] = float(main.max_abs_diff_shapley_vs_max_res.max())


# ---------------------------------------------------------------- beyond
def beyond_analysis(props, per):
    votes = pd.read_csv(PROC / "votes.csv")
    games, ind = participation_games(props, votes, Q, CONFIG["power"]["resolution"])
    games = games.merge(per[["proposal_id", "top1_shapley", "top1_banzhaf"]].rename(
        columns={"top1_shapley": "top1_shapley_all", "top1_banzhaf": "top1_banzhaf_all"}), on="proposal_id")
    games.to_csv(RES / "participation_games.csv", index=False)
    ind.to_csv(RES / "participation_indices.csv.gz", index=False)
    ok = games[~games.no_winning_coalition]
    SUMMARY.update({
        "part_games": len(games), "part_no_winning": int(games.no_winning_coalition.sum()),
        "part_quorum_binds": int(games.quorum_binds.sum()),
        "part_voters_median": float(games.n_voters.median()),
        "part_top1_share_median": float(ok.top1_share.median()),
        "part_top1_banzhaf_median": float(ok.top1_banzhaf.median()),
        "part_top1_shapley_median": float(ok.top1_shapley.median()),
        "part_nakamoto_shapley_median": float(ok.nakamoto_shapley.median()),
        "part_top1_shapley_gt_all_share": float((ok.top1_shapley > ok.top1_shapley_all).mean()),
    })

    # Prior work on our data. Fritsch et al. measure at block 14,300,000; we use
    # the latest of our snapshots at or before that block.
    w = pd.read_csv(PROC / "weights.csv.gz")
    snaps = props[props.snapshot_block <= 14_300_000].sort_values("snapshot_block")
    pid = int(snaps.proposal_id.iloc[-1])
    wf = w[(w.proposal_id == pid) & (w.weight > 0)]
    v2h = voters_to_half(votes)
    v2h = v2h[v2h.index.isin(props[props.outcome != "canceled"].proposal_id)]
    prior = pd.DataFrame([
        {"source": "Fritsch et al. 2204.01176", "metric": "Nakamoto coefficient (delegates)",
         "their_value": "8 (Compound, block 14,300,000)",
         "our_value": nakamoto(wf.weight), "our_scope": f"snapshot block {int(snaps.snapshot_block.iloc[-1])} (proposal {pid})"},
        {"source": "Messias et al. 2305.17655", "metric": "mean voters needed for >= 50% of votes cast",
         "their_value": "3.18 (Compound, to Aug 2024)",
         "our_value": round(float(v2h.mean()), 2), "our_scope": f"{len(v2h)} decided Bravo proposals"},
    ])
    g_del = gini(wf.weight)
    prior = pd.concat([prior, pd.DataFrame([
        {"source": "Fritsch et al. 2204.01176", "metric": "Gini coefficient of delegates",
         "their_value": "0.987 (Compound, block 14,300,000)", "our_value": round(g_del, 3),
         "our_scope": f"snapshot block {int(snaps.snapshot_block.iloc[-1])} (proposal {pid})"}])])
    prior.to_csv(RES / "prior_work_comparison.csv", index=False)
    SUMMARY["gini_delegates_at_fritsch_block"] = g_del

    # Fritsch et al.'s potential / exercised power on our data.
    fp = fritsch_power(props, votes, Q)
    fp.to_csv(RES / "fritsch_power_per_vote.csv.gz", index=False)
    # Sanity check: a voter with potential power is a one-address flip set, so
    # every such proposal must have min_flip_size == 1 in pivotal_per_proposal.
    piv = pd.read_csv(RES / "pivotal_per_proposal.csv").set_index("proposal_id")
    with_pot = fp[fp.potential].proposal_id.unique()
    assert (piv.loc[with_pot, "min_flip_size"] == 1).all(), "potential power disagrees with flip sets"
    per_voter = fp.groupby("voter").agg(n_voted=("proposal_id", "size"), potential=("potential", "sum"),
                                         exercised=("exercised", "sum"))
    # Average participation-game Shapley-Shubik per voter (0 where it did not vote).
    pss = ind.groupby("address").shapley.sum() / len(games)
    per_voter["avg_participation_shapley"] = pss.reindex(per_voter.index).fillna(0)
    per_voter = per_voter.sort_values("potential", ascending=False)
    per_voter.to_csv(RES / "fritsch_power_per_voter.csv")
    early = fp[fp.proposal_id.isin(props[props.snapshot_block <= 14_300_000].proposal_id)]
    early_v = early.groupby("voter").agg(n_voted=("proposal_id", "size"), potential=("potential", "sum"))
    top_early = early_v.sort_values(["potential", "n_voted"], ascending=False).iloc[0]
    active = per_voter[per_voter.n_voted >= 5]
    SUMMARY.update({
        "fritsch_proposals_with_potential": int(len(with_pot)),
        "fritsch_proposals_with_exercised": int(fp[fp.exercised].proposal_id.nunique()),
        "fritsch_voters_with_potential": int((per_voter.potential > 0).sum()),
        "fritsch_voters_total": len(per_voter),
        "fritsch_top_voter_potential": int(per_voter.potential.iloc[0]),
        "fritsch_top_voter_voted": int(per_voter.n_voted.iloc[0]),
        "fritsch_top4_potential_share": float(per_voter.potential.head(4).sum() / per_voter.potential.sum()),
        "fritsch_early_proposals": int(early.proposal_id.nunique()),
        "fritsch_early_top_potential": int(top_early.potential), "fritsch_early_top_voted": int(top_early.n_voted),
        "fritsch_spearman_potential_vs_shapley": spearman(active.potential / active.n_voted,
                                                          active.avg_participation_shapley),
        "fritsch_active_voters": len(active),
    })
    SUMMARY.update({"fritsch_block_pid": pid, "fritsch_snapshot_block": int(snaps.snapshot_block.iloc[-1]),
                    "nakamoto_at_fritsch_block": nakamoto(wf.weight),
                    "voters_to_half_mean": float(v2h.mean()), "voters_to_half_median": float(v2h.median()),
                    "voters_to_half_n": len(v2h)})

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(games.proposal_id, games.top1_shapley_all, color=INK2, lw=1.5,
            label="All delegates (main game)")
    ax.plot(ok.proposal_id, ok.top1_shapley, color=ORANGE, lw=1.2, marker="o", ms=3,
            label="Only those who voted (participation game)")
    ax.set(xlabel="Proposal id", ylabel="Shapley-Shubik of largest player", ylim=(0, 1),
           title="Largest player's power: everyone vs actual voters")
    ax.legend(loc="upper left")
    save(fig, "fig_participation_power.png")
    return games


# ---------------------------------------------------------------- figures
def figures(per, agg, piv, props):
    x = per.proposal_id

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(x, per.top1_share, color=INK2, lw=1.5, label="Token (voting-weight) share")
    ax.plot(x, per.top1_banzhaf, color=BLUE, label="Banzhaf index")
    ax.plot(x, per.top1_shapley, color=ORANGE, label="Shapley-Shubik index")
    ax.set(xlabel="Proposal id", ylabel="Largest single delegate", ylim=(0, None),
           title="Largest delegate: token share vs power, per proposal")
    ax.legend(loc="lower right")
    save(fig, "fig_top1_power.png")

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(x, per.top5_share, color=INK2, lw=1.5, label="Token share")
    ax.plot(x, per.top5_banzhaf, color=BLUE, label="Banzhaf")
    ax.plot(x, per.top5_shapley, color=ORANGE, label="Shapley-Shubik")
    ax.set(xlabel="Proposal id", ylabel="Combined top-5 delegates", ylim=(0, 1),
           title="Top-5 delegates: token share vs power, per proposal")
    ax.legend(loc="lower right")
    save(fig, "fig_top5_power.png")

    # Only addresses well above the rounding unit (1/resolution of total weight).
    top = agg[agg.share >= 4 / CONFIG["power"]["resolution"]]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axhline(1, color=INK2, lw=1, ls="--")
    ax.text(top.share.max(), 1.005, "index = token share ", color=INK2, va="bottom", ha="right", fontsize=9)
    ax.scatter(top.share, top.banzhaf / top.share, s=24, color=BLUE, edgecolor=SURFACE, lw=0.8,
               label="Banzhaf / share", zorder=3)
    ax.scatter(top.share, top.shapley / top.share, s=24, color=ORANGE, edgecolor=SURFACE, lw=0.8,
               label="Shapley-Shubik / share", zorder=3)
    ax.set(xscale="log", xlabel=f"Average token share (log scale), {len(top)} delegates with share ≥ 4 rounding units",
           ylabel="Power per unit of token share", ylim=(0.85, 1.2),
           title="Effective power relative to nominal share")
    ax.legend(loc="lower right")
    save(fig, "fig_gap_scatter.png")

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(x, per.tv_share_banzhaf, color=BLUE, label="Banzhaf vs token share")
    ax.plot(x, per.tv_share_shapley, color=ORANGE, label="Shapley-Shubik vs token share")
    ax.plot(x, per.tv_banzhaf_shapley, color=AQUA, label="Banzhaf vs Shapley-Shubik")
    ax.set(xlabel="Proposal id", ylabel="Total-variation distance", ylim=(0, None),
           title="How far apart are the three power distributions?")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=9)
    save(fig, "fig_distribution_distance.png")

    top10 = agg.head(10)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    pos = np.arange(len(top10))
    for j, (col, c, lab) in enumerate([("share", INK2, "Token share"), ("banzhaf", BLUE, "Banzhaf"),
                                       ("shapley", ORANGE, "Shapley-Shubik")]):
        ax.bar(pos + (j - 1) * 0.27, top10[col], width=0.25, color=c, label=lab, edgecolor=SURFACE, lw=1)
    ax.set_xticks(pos, [short(a) for a in top10.index], rotation=35, ha="right", fontsize=9)
    ax.set(ylabel="Average over proposals", title="Ten largest delegates: tokens vs power")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    save(fig, "fig_top10_delegates.png")

    a = piv[piv.analysed]
    counts = a.min_flip_size.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(counts.index.astype(int).astype(str), counts.values, color=BLUE, edgecolor=SURFACE, lw=2)
    for i, v in enumerate(counts.values):
        ax.text(i, v, str(v), ha="center", va="bottom", color=INK)
    ax.set(xlabel="Fewest addresses whose votes would have reversed the outcome",
           ylabel="Decided proposals", title="Minimal decisive set size")
    ax.grid(axis="x", visible=False)
    save(fig, "fig_min_flip_size.png")

    fig, ax = plt.subplots(figsize=(7, 4))
    shares = [a[f"top{k}_flips"].mean() for k in TOPK]
    labels = [f"top {k}" for k in TOPK]
    ax.bar(labels, shares, color=BLUE, edgecolor=SURFACE, lw=2)
    for i, v in enumerate(shares):
        ax.text(i, v, f"{v:.0%}", ha="center", va="bottom", color=INK)
    ax.set(ylim=(0, 1.08), ylabel="Share of decided proposals",
           title="Could the top-k delegates alone have reversed the outcome?")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.grid(axis="x", visible=False)
    save(fig, "fig_topk_pivotal.png")


def write_tex_macros():
    """results/numbers.tex: every number quoted in the slides, as LaTeX macros."""
    S = SUMMARY
    pct = lambda x: f"{100 * x:.1f}\\%"
    m = {
        "NProposals": S["proposals_total"], "NExecuted": S["outcomes"].get("executed", 0),
        "NDefeated": S["outcomes"].get("defeated", 0), "NCanceled": S["outcomes"].get("canceled", 0),
        "NDecided": S["decided_proposals"], "NVotes": f"{S['votes_total']:,}",
        "NPlayers": f"{S['players_median']:,.0f}", "NLive": f"{S['nondummy_players_median']:.0f}",
        "TopOneShare": pct(S["top1_share_median"]), "TopOneBz": pct(S["top1_banzhaf_median"]),
        "TopOneSS": pct(S["top1_shapley_median"]), "TopFiveShare": pct(S["top5_share_median"]),
        "TopFiveBz": pct(S["top5_banzhaf_median"]), "TopFiveSS": pct(S["top5_shapley_median"]),
        "NakShare": f"{S['nakamoto_share_median']:.0f}", "NakSS": f"{S['nakamoto_shapley_median']:.0f}",
        "MaxGapBz": f"{100 * S['max_abs_gap_banzhaf']:.1f}", "MaxGapSS": f"{100 * S['max_abs_gap_shapley']:.1f}",
        "TVBzSS": f"{S['tv_banzhaf_shapley_median']:.3f}", "TVBzSSmax": f"{S['tv_banzhaf_shapley_max']:.3f}",
        "TVShareBz": f"{S['tv_share_banzhaf_median']:.3f}", "TVShareSS": f"{S['tv_share_shapley_median']:.3f}",
        "SpearmanMin": f"{S['spearman_bz_ss_min']:.3f}",
        "FlipOne": S["min_flip_size_counts"].get(1, 0), "FlipMedian": f"{S['min_flip_size_median']:.0f}",
        "FlipMax": max(S["min_flip_size_counts"]),
        "TopkOne": pct(S["topk_flip_share"][1]), "TopkThree": pct(S["topk_flip_share"][3]),
        "TopkFive": pct(S["topk_flip_share"][5]), "TopkTen": pct(S["topk_flip_share"][10]),
        "Turnout": pct(S["turnout_share_median"]),
        "ResDiff": f"{max(S['resolution_sensitivity_max_diff_banzhaf'], S['resolution_sensitivity_max_diff_shapley']):.5f}",
        "TransMoved": pct(S["transitive_max_weight_moved_share"]),
        "DummyMax": pct(S["dummy_weight_share_max"]),
        "RatioTopMin": f"{S['ratio_top2_min']:.2f}", "RatioTopMax": f"{S['ratio_top2_max']:.2f}",
        "RatioRest": f"{S['ratio_rest_median_banzhaf']:.2f}", "RatioRestBelow": pct(S["ratio_rest_below_one_share"]),
        "RatioRestN": S["ratio_rest_n"],
        "BzOverSSFrom": S["bz_over_ss_from_proposal"], "BzOverSSDate": S["bz_over_ss_from_date"],
        "BzOverSSMinGap": f"{100 * S['bz_over_ss_min_gap_after']:.1f}",
        "NTransfers": f"{S['events']['Transfer'] / 1e6:.2f}M", "NDelegationEvents": f"{S['events']['DelegateChanged']:,}",
        "RawMB": f"{S['raw_mb']:.0f}",
        "FirstDate": S["first_start_date"], "LastDate": S["last_start_date"],
        "FritschDate": S["fritsch_cutoff_date"], "EndDate": S["end_block_date"],
        "TopOneExceeds": pct(min(S["top1_banzhaf_exceeds_share_share"], S["top1_shapley_exceeds_share_share"])),
        "DelegMismatch": S["delegate_weight_mismatches"],
        "StateMismatch": S["outcome_state_mismatches"],
        "TallyDiff": f"{S['max_tally_diff_vs_onchain_COMP']:.0e}",
        "PartGames": S["part_games"], "PartNoWin": S["part_no_winning"], "PartQuorumBinds": S["part_quorum_binds"],
        "PartVoters": f"{S['part_voters_median']:.0f}",
        "PartTopOneShare": pct(S["part_top1_share_median"]), "PartTopOneBz": pct(S["part_top1_banzhaf_median"]),
        "PartTopOneSS": pct(S["part_top1_shapley_median"]), "PartNakSS": f"{S['part_nakamoto_shapley_median']:.0f}",
        "PartTopOneGreater": pct(S["part_top1_shapley_gt_all_share"]),
        "NakFritsch": S["nakamoto_at_fritsch_block"], "FritschBlock": f"{S['fritsch_snapshot_block']:,}",
        "VotersHalf": f"{S['voters_to_half_mean']:.2f}",
        "GiniFritsch": f"{S['gini_delegates_at_fritsch_block']:.3f}",
        "PotProposals": S["fritsch_proposals_with_potential"], "ExProposals": S["fritsch_proposals_with_exercised"],
        "PotVoters": S["fritsch_voters_with_potential"], "PotVotersTotal": f"{S['fritsch_voters_total']:,}",
        "PotTopFour": pct(S["fritsch_top4_potential_share"]),
        "PotTop": S["fritsch_top_voter_potential"], "PotTopVoted": S["fritsch_top_voter_voted"],
        "PotEarlyN": S["fritsch_early_proposals"], "PotEarlyTop": S["fritsch_early_top_potential"],
        "PotEarlyTopVoted": S["fritsch_early_top_voted"],
        "PotSpearman": f"{S['fritsch_spearman_potential_vs_shapley']:.2f}", "PotActive": S["fritsch_active_voters"], "VotersHalfN": S["voters_to_half_n"], "VoteMismatch": S["vote_weight_mismatches"],
    }
    piv = pd.read_csv(RES / "pivotal_per_proposal.csv")
    d = piv[piv.analysed & (piv.outcome == "defeated")]
    m["DefeatedFlipOne"] = int((d.min_flip_size == 1).sum())
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in m.items()]
    (RES / "numbers.tex").write_text("% generated by analysis/run_all.py; do not edit\n" + "\n".join(lines) + "\n")


def main():
    RES.mkdir(exist_ok=True)
    props = pd.read_csv(PROC / "proposals.csv")
    data_summary(props)
    transitive_check()
    ind, games = compute(CONFIG["power"]["resolution"])
    per, agg = gap_analysis(ind, games, props)
    piv = pivotal_analysis(props)
    resolution_sensitivity(props)
    figures(per, agg, piv, props)
    beyond_analysis(props, per)
    write_tex_macros()
    (RES / "summary.json").write_text(json.dumps(SUMMARY, indent=2, default=float))
    print(json.dumps(SUMMARY, indent=2, default=float))


if __name__ == "__main__":
    main()
