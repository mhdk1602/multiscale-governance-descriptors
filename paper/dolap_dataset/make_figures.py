"""Regenerate every figure and table for the DOLAP longitudinal-lineage dataset paper.

Reads only the released artifacts under ``artifacts/phase_4/`` and writes to
``paper/dolap_dataset/figures/`` (PDF + PNG) and ``paper/dolap_dataset/tables/``
(CSV + booktabs LaTeX).

Run from anywhere:

    PYTHONPATH=src /usr/bin/python3 paper/dolap_dataset/make_figures.py

No step in this script is stochastic. ``SEED`` is set anyway so that adding a
resampled or jittered panel later cannot silently break reproducibility. The
underlying descriptors do contain one stochastic step, Louvain in
``resolution_sweep``, which is seeded at 42 inside the descriptor library.

Three figures the brief asked for are not produced. The phase-4 snapshots record
graph-level scalars only, with no per-node rows, so layer composition,
documentation/test coverage, and degree distributions cannot be recovered from
the release. See DROPPED_FIGURES below.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

SEED = 42
np.random.seed(SEED)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "phase_4"
OUT_DIR = Path(__file__).resolve().parent
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"

PROJECTS = ["cal-itp", "mattermost"]
LABELS = {"cal-itp": "Cal-ITP", "mattermost": "Mattermost"}

# Okabe-Ito. Colourblind-safe, and the two project series are additionally
# separated by line style and marker so the figures survive greyscale printing.
COLOR = {"cal-itp": "#0072B2", "mattermost": "#D55E00"}
STYLE = {"cal-itp": "-", "mattermost": "--"}
MARKER = {"cal-itp": "o", "mattermost": "s"}
DESC_COLOR = {
    "D1_csi": "#0072B2",
    "D3_alg_conn": "#D55E00",
    "D4_cycle_rank_norm": "#009E73",
    "D1_n_comm": "#CC79A7",
    "D2_max_gini": "#E69F00",
    "D3_norm_gap": "#56B4E9",
    "D3_fiedler_bim": "#666666",
}

# ACM sigconf single-column text width is 241.14pt.
COL_W = 3.33
FULL_W = 7.0

DRIFT_DESCRIPTORS = ["D1_csi", "D3_alg_conn", "D4_cycle_rank_norm"]
DRIFT_THRESHOLD_PCT = 20.0
SAMPLING_WINDOW_DAYS = 30

DROPPED_FIGURES = [
    (
        "Layer composition over time",
        "The snapshots carry no layer attribute. exp_longitudinal_dbt.py builds each "
        "graph by regex-matching ref() calls in .sql files and stores only N, M and the "
        "D1-D4 scalars, so no model is ever labelled source/staging/intermediate/mart. "
        "data/dbt_nodes.csv does have a layer column, but it is a single anonymized "
        "cross-section of a different 223-node project taken on 2026-05-04, not a "
        "series over either longitudinal project.",
    ),
    (
        "Documentation and test coverage trajectories",
        "Same cause. has_documentation and has_tests exist only in the cross-sectional "
        "data/dbt_nodes.csv. The longitudinal extractor never reads .yml schema files, "
        "so coverage was never measured per snapshot.",
    ),
    (
        "Degree distribution, first snapshot against last",
        "Per-node degrees are not retained. Each snapshot is reduced to scalars at "
        "extraction time and the graphs themselves are not serialised, so no degree "
        "sequence survives in the release. Reconstructing one would mean re-cloning both "
        "upstream repositories and replaying 106 checkouts, which the brief excludes. "
        "figA_density_evolution substitutes the mean-degree and density trajectories, "
        "which are exact arithmetic on the released N and M and are not a degree "
        "distribution.",
    ),
]


# --------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------

def load_longitudinal():
    """Return {project: DataFrame}, date-parsed and validated."""
    frames = {}
    for project in PROJECTS:
        path = ARTIFACT_DIR / f"longitudinal_{project}.csv"
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])
        if not df["date"].is_monotonic_increasing:
            raise ValueError(f"{path} is not sorted by date")
        if df[["N", "M"]].isna().any().any():
            raise ValueError(f"{path} has missing N or M")
        frames[project] = df
    return frames


def recompute_drift(frames):
    """Re-derive the >20% step-change events from the longitudinal CSVs."""
    rows = []
    for project in PROJECTS:
        df = frames[project]
        for desc in DRIFT_DESCRIPTORS:
            s = pd.to_numeric(df[desc], errors="coerce")
            pct = (s.diff().abs() / s.shift(1).abs()) * 100.0
            for i in pct.index[pct > DRIFT_THRESHOLD_PCT]:
                rows.append(
                    {
                        "project": project,
                        "date": df["date"].iloc[i].strftime("%Y-%m-%d"),
                        "descriptor": desc,
                        "prev": s.iloc[i - 1],
                        "curr": s.iloc[i],
                        "pct_change": pct.iloc[i],
                    }
                )
    return pd.DataFrame(rows)


def load_drift(frames):
    """Load the released drift table and assert it reproduces from the snapshots."""
    released = pd.read_csv(ARTIFACT_DIR / "drift_events_refined.csv")
    key = ["project", "descriptor", "date"]
    lhs = released[key + ["pct_change"]].sort_values(key).reset_index(drop=True)
    rhs = recompute_drift(frames)[key + ["pct_change"]].sort_values(key).reset_index(drop=True)
    if lhs.shape != rhs.shape:
        raise ValueError(
            f"drift_events_refined.csv has {len(lhs)} rows but {len(rhs)} reproduce "
            f"from the snapshots at a {DRIFT_THRESHOLD_PCT:.0f}% threshold"
        )
    if not (lhs[key].values == rhs[key].values).all():
        raise ValueError("drift_events_refined.csv does not reproduce, keys differ")
    if not np.allclose(lhs["pct_change"], rhs["pct_change"]):
        raise ValueError("drift_events_refined.csv does not reproduce, magnitudes differ")
    released["date"] = pd.to_datetime(released["date"])
    return released


def drift_dates(drift, project):
    """Unique dates on which at least one descriptor drifted, sorted."""
    return np.sort(drift.loc[drift["project"] == project, "date"].unique())


# --------------------------------------------------------------------------
# Style
# --------------------------------------------------------------------------

def set_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "lines.linewidth": 1.1,
            "lines.markersize": 2.4,
            "grid.linewidth": 0.4,
            "grid.alpha": 0.30,
            "grid.color": "#999999",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            # Type 42 keeps fonts TrueType. Type 3 fails ACM and IEEE PDF checks.
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def year_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=(1, 7)))


def plain_log_ticks(axis, ticks):
    """Label a log axis with plain numbers. Matplotlib's default 10^k labels leave
    most of these ranges with a single tick."""
    axis.set_major_locator(FixedLocator(ticks))
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    axis.set_minor_formatter(NullFormatter())


def panel_tag(ax, tag):
    ax.text(
        -0.16, 1.04, tag, transform=ax.transAxes,
        fontsize=8, fontweight="bold", va="bottom", ha="left",
    )


def save(fig, stem):
    pdf = FIG_DIR / f"{stem}.pdf"
    png = FIG_DIR / f"{stem}.png"
    fig.savefig(pdf)
    fig.savefig(png, dpi=300)
    plt.close(fig)
    return [pdf, png]


def ecdf(values):
    """Step coordinates for an empirical CDF, anchored at y=0."""
    x = np.sort(np.asarray(values, dtype=float))
    y = np.arange(1, len(x) + 1) / len(x)
    return np.concatenate([x[:1], x]), np.concatenate([[0.0], y])


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def fig_growth_trajectories(frames, drift):
    """Anchor figure. Node and edge counts over time with drift events marked."""
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.9), sharex=True)

    for ax, col, ylabel in [(axes[0], "N", "Nodes $N$"), (axes[1], "M", "Edges $M$")]:
        for project in PROJECTS:
            df = frames[project]
            ax.plot(
                df["date"], df[col],
                STYLE[project], color=COLOR[project], marker=MARKER[project],
                label=LABELS[project],
            )
        ax.set_ylabel(ylabel)
        ax.grid(axis="y")
        # Reserve a gutter below zero for the drift rug so the ticks never collide
        # with the early Mattermost series, which starts near the axis floor.
        top = max(frames[p][col].max() for p in PROJECTS)
        ax.set_ylim(-0.17 * top, 1.06 * top)
        ax.set_yticks([t for t in ax.get_yticks() if 0 <= t <= top])
        for row, project in enumerate(PROJECTS):
            dates = drift_dates(drift, project)
            ax.vlines(
                dates, 0.012 + row * 0.058, 0.058 + row * 0.058,
                transform=ax.get_xaxis_transform(),
                color=COLOR[project], linewidth=0.7,
            )

    year_axis(axes[1])
    axes[1].set_xlabel("Snapshot date")
    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")

    handles, labels = axes[0].get_legend_handles_labels()
    rug = plt.Line2D([], [], color="#444444", linewidth=0.7, linestyle="-")
    axes[0].legend(
        handles + [rug],
        labels + [f"drift event ({len(drift)})"],
        loc="upper left", handlelength=1.6, borderaxespad=0.2,
    )
    fig.align_ylabels(axes)
    fig.tight_layout(pad=0.3)
    return save(fig, "fig1_growth_trajectories")


def fig_density_evolution(frames):
    """Substitute for the dropped degree-distribution figure.

    Mean out-degree M/N and DAG edge density M/(N(N-1)). Both are exact
    functions of the released N and M. Neither is a degree distribution.
    """
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.5), sharex=True)

    for project in PROJECTS:
        df = frames[project]
        n = df["N"].astype(float)
        m = df["M"].astype(float)
        axes[0].plot(
            df["date"], m / n,
            STYLE[project], color=COLOR[project], marker=MARKER[project],
            label=LABELS[project],
        )
        axes[1].plot(
            df["date"], m / (n * (n - 1)),
            STYLE[project], color=COLOR[project], marker=MARKER[project],
        )

    axes[0].set_ylabel("Mean degree $M/N$")
    axes[1].set_ylabel(r"Density $\frac{M}{N(N-1)}$")
    axes[1].set_yscale("log")
    plain_log_ticks(axes[1].yaxis, [0.002, 0.005, 0.01, 0.02, 0.05])
    for ax in axes:
        ax.grid(axis="y")
    axes[0].set_ylim(bottom=0)
    year_axis(axes[1])
    axes[1].set_xlabel("Snapshot date")
    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    axes[0].legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)
    fig.align_ylabels(axes)
    fig.tight_layout(pad=0.3)
    return save(fig, "figA_density_evolution")


def fig_drift_characterization(drift):
    """Magnitude by descriptor and inter-arrival time by project, both as ECDFs.

    With 44 events split three ways an ECDF reports the whole sample without the
    bin-width choice a histogram would impose.
    """
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.9))

    ax = axes[0]
    for desc in DRIFT_DESCRIPTORS:
        vals = drift.loc[drift["descriptor"] == desc, "pct_change"].values
        x, y = ecdf(vals)
        ax.step(
            x, y, where="post", color=DESC_COLOR[desc],
            label=f"{desc.replace('_', ' ')} ($n$={len(vals)})",
        )
    ax.axvline(DRIFT_THRESHOLD_PCT, color="#999999", linewidth=0.6, linestyle=":")
    ax.text(
        DRIFT_THRESHOLD_PCT, 1.02, "threshold",
        fontsize=6, color="#666666", ha="left", va="bottom",
    )
    ax.set_xscale("log")
    plain_log_ticks(ax.xaxis, [20, 30, 50, 100, 200])
    ax.set_xlabel("Relative change at event (%)")
    ax.set_ylabel("ECDF")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y")
    ax.legend(loc="lower right", handlelength=1.6, borderaxespad=0.2)

    ax = axes[1]
    for project in PROJECTS:
        dates = drift_dates(drift, project)
        gaps = np.diff(dates).astype("timedelta64[D]").astype(float)
        x, y = ecdf(gaps)
        ax.step(
            x, y, where="post", color=COLOR[project], linestyle=STYLE[project],
            label=f"{LABELS[project]} ($n$={len(gaps)})",
        )
    ax.set_xlabel("Days between consecutive drift events")
    ax.set_ylabel("ECDF")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y")
    ax.legend(loc="lower right", handlelength=1.6, borderaxespad=0.2)

    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    fig.align_ylabels(axes)
    fig.tight_layout(pad=0.3)
    return save(fig, "fig5_drift_characterization")


def fig_snapshot_cadence(frames):
    """Where snapshots fall, and how far apart they are.

    Sampling is one commit per 30-day window of commits that touch the models
    path. A window with no such commit yields no snapshot, so the series is not
    evenly spaced and the gaps are the honest limitation.
    """
    fig, axes = plt.subplots(
        2, 1, figsize=(COL_W, 3.3), gridspec_kw={"height_ratios": [1.0, 1.7]}
    )

    ax = axes[0]
    for row, project in enumerate(PROJECTS):
        dates = frames[project]["date"]
        ax.vlines(
            dates, row - 0.30, row + 0.30,
            color=COLOR[project], linewidth=0.7,
        )
    ax.set_yticks(range(len(PROJECTS)))
    ax.set_yticklabels(
        [f"{LABELS[p]}\n($n$={len(frames[p])})" for p in PROJECTS], fontsize=6.5
    )
    ax.set_ylim(-0.65, len(PROJECTS) - 0.25)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    year_axis(ax)
    ax.set_xlabel("Snapshot date", labelpad=1)

    # Call out the single worst hole in the series, anchored mid-gap.
    worst_project, worst_gap, worst_at = None, -1.0, None
    for project in PROJECTS:
        d = frames[project]["date"]
        g = d.diff().dt.days
        i = int(g.idxmax())
        if g.max() > worst_gap:
            worst_gap = float(g.max())
            worst_at = d.iloc[i - 1] + (d.iloc[i] - d.iloc[i - 1]) / 2
            worst_project = project
    ax.annotate(
        f"{worst_gap:.0f}-day gap",
        xy=(worst_at, PROJECTS.index(worst_project) + 0.30),
        xytext=(0, 6), textcoords="offset points",
        fontsize=6, color="#333333", ha="center",
        arrowprops=dict(arrowstyle="-", linewidth=0.5, color="#333333"),
    )

    ax = axes[1]
    for project in PROJECTS:
        gaps = frames[project]["date"].diff().dt.days.dropna().values
        x, y = ecdf(gaps)
        ax.step(
            x, y, where="post", color=COLOR[project], linestyle=STYLE[project],
            label=f"{LABELS[project]} (med {np.median(gaps):.0f} d)",
        )
    ax.axvline(SAMPLING_WINDOW_DAYS, color="#999999", linewidth=0.6, linestyle=":")
    ax.text(
        SAMPLING_WINDOW_DAYS, 1.02, "30-day target",
        fontsize=6, color="#666666", ha="left", va="bottom",
    )
    ax.set_xlabel("Days between consecutive snapshots")
    ax.set_ylabel("ECDF")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y")
    ax.legend(loc="lower right", handlelength=1.6, borderaxespad=0.2)

    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    fig.tight_layout(pad=0.3, h_pad=0.6)
    # The timeline's y-tick labels are wider than "ECDF", so tight_layout leaves the
    # two panels on different left edges. Snap them to a common plot box.
    boxes = [ax.get_position() for ax in axes]
    left = max(b.x0 for b in boxes)
    right = min(b.x1 for b in boxes)
    for ax, box in zip(axes, boxes):
        ax.set_position([left, box.y0, right - left, box.height])
    return save(fig, "fig6_snapshot_cadence")


def fig_descriptor_trajectories(frames):
    """All seven released descriptors over time. Two-column figure."""
    descs = [
        ("D1_csi", "D1 community stability"),
        ("D1_n_comm", r"D1 communities at $\gamma$=1"),
        ("D2_max_gini", "D2 max blast-radius Gini"),
        ("D3_alg_conn", "D3 algebraic connectivity"),
        ("D3_norm_gap", "D3 normalized spectral gap"),
        ("D3_fiedler_bim", "D3 Fiedler bimodality"),
        ("D4_cycle_rank_norm", "D4 normalized cycle rank"),
    ]
    fig, axes = plt.subplots(4, 2, figsize=(FULL_W, 5.4), sharex=True)
    flat = axes.ravel()

    for ax, (col, title) in zip(flat, descs):
        for project in PROJECTS:
            df = frames[project]
            ax.plot(
                df["date"], df[col],
                STYLE[project], color=COLOR[project], marker=MARKER[project],
                label=LABELS[project],
            )
        ax.set_title(title, fontsize=7.5, pad=3)
        ax.grid(axis="y")
        ax.tick_params(labelsize=6.5)

    flat[-1].axis("off")
    handles, labels = flat[0].get_legend_handles_labels()
    flat[-1].legend(handles, labels, loc="center", handlelength=2.0, fontsize=8)

    for ax in axes[-1, :]:
        year_axis(ax)
    year_axis(axes[-2, 1])
    axes[-2, 1].tick_params(labelbottom=True, labelsize=6.5)
    axes[-1, 0].set_xlabel("Snapshot date")
    fig.tight_layout(pad=0.4)
    return save(fig, "figB_descriptor_trajectories")


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def tex_escape(text):
    out = str(text).replace("\\", r"\textbackslash{}")
    for char, repl in [
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
        ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]:
        out = out.replace(char, repl)
    # Second pass, after $ has been escaped. In OT1/T1 text mode < > | render as
    # inverted punctuation rather than the intended glyph, so they need math mode.
    for char, repl in [
        ("≥", r"$\geq$"), ("≤", r"$\leq$"),
        ("<", r"\textless{}"), (">", r"\textgreater{}"), ("|", r"\textbar{}"),
    ]:
        out = out.replace(char, repl)
    return out


def tex_int(value):
    """Thousands separator in the form the existing preprints use."""
    return f"{int(value):,}".replace(",", "{,}")


def write_table(stem, frame, tex_body):
    csv_path = TAB_DIR / f"{stem}.csv"
    tex_path = TAB_DIR / f"{stem}.tex"
    frame.to_csv(csv_path, index=False)
    tex_path.write_text(tex_body)
    return [csv_path, tex_path]


def table_dataset_characterization(frames, drift):
    rows = []
    for project in PROJECTS:
        df = frames[project]
        n_first, n_last = int(df["N"].iloc[0]), int(df["N"].iloc[-1])
        m_first, m_last = int(df["M"].iloc[0]), int(df["M"].iloc[-1])
        peak_i = int(df["N"].idxmax())
        span_days = int((df["date"].max() - df["date"].min()).days)
        rows.append(
            {
                "project": LABELS[project],
                "snapshots": len(df),
                "date_start": df["date"].min().strftime("%Y-%m-%d"),
                "date_end": df["date"].max().strftime("%Y-%m-%d"),
                "span_days": span_days,
                "span_years": round(span_days / 365.25, 2),
                "nodes_first": n_first,
                "nodes_last": n_last,
                "nodes_min": int(df["N"].min()),
                "nodes_max": int(df["N"].max()),
                "nodes_peak_date": df["date"].iloc[peak_i].strftime("%Y-%m-%d"),
                "edges_first": m_first,
                "edges_last": m_last,
                "edges_min": int(df["M"].min()),
                "edges_max": int(df["M"].max()),
                "node_growth_multiple": round(n_last / n_first, 2),
                "edge_growth_multiple": round(m_last / m_first, 2),
                "net_contraction_from_peak_pct": round(
                    100.0 * (1.0 - n_last / df["N"].max()), 1
                ),
                "drift_events": int((drift["project"] == project).sum()),
                "drift_event_dates": int(len(drift_dates(drift, project))),
                "median_snapshot_gap_days": float(
                    df["date"].diff().dt.days.dropna().median()
                ),
                "max_snapshot_gap_days": float(df["date"].diff().dt.days.dropna().max()),
            }
        )
    frame = pd.DataFrame(rows)

    # Round once, at the end. Summing per-project rounded years and rounding again
    # moves the corpus total off the 9.0 the rest of the repository reports.
    cumulative_years = float(frame["span_days"].sum()) / 365.25
    total = {
        "project": "All",
        "snapshots": int(frame["snapshots"].sum()),
        "date_start": frame["date_start"].min(),
        "date_end": frame["date_end"].max(),
        "span_days": int(frame["span_days"].sum()),
        "span_years": round(cumulative_years, 3),
        "drift_events": int(len(drift)),
        "drift_event_dates": int(frame["drift_event_dates"].sum()),
    }
    frame = pd.concat([frame, pd.DataFrame([total])], ignore_index=True)
    # The All row has no per-project counts, which would otherwise upcast the count
    # columns to float and write "74.0" where the source says 74.
    for col in frame.columns:
        if col.startswith(("nodes_", "edges_")) and not col.endswith("_date"):
            frame[col] = frame[col].astype("Int64")

    # Neither project is monotone. Record the peaks so the growth multiples are not
    # read as the full range each graph traverses.
    note = (
        "Neither series is monotone. "
        + ". ".join(
            "{p} peaks at $N$={n} ({d}) and $M$={m}".format(
                p=r["project"],
                n=tex_int(r["nodes_max"]),
                d=r["nodes_peak_date"][:7],
                m=tex_int(r["edges_max"]),
            )
            for r in rows
        )
        + ". Mattermost ends {c}\\% below its own peak.".format(
            c=f"{rows[1]['net_contraction_from_peak_pct']:.1f}"
        )
    )
    caption = [
        r"  \caption{Longitudinal dbt lineage corpus. One snapshot per 30-day window",
        r"    of commits touching the models path. Growth is the last snapshot over",
        r"    the first. Drift counts descriptor-level step changes above 20\%.}",
        r"  \label{tab:dataset}",
    ]

    # Row-per-project. The full column set measures 291pt against a 241pt ACM
    # sigconf column, so this one is a two-column float.
    wide = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table*}[t]",
        r"  \centering",
        r"  \footnotesize",
        *caption,
        r"  \begin{tabular}{lrlrrrrrrr}",
        r"    \toprule",
        r"    & & & \multicolumn{2}{c}{Nodes $N$} & \multicolumn{2}{c}{Edges $M$}"
        r" & & & \\",
        r"    \cmidrule(lr){4-5}\cmidrule(lr){6-7}",
        r"    Project & Snap. & Date span & first$\to$last & min--max"
        r" & first$\to$last & min--max & $N\times$ & $M\times$ & Drift \\",
        r"    \midrule",
    ]
    for r in rows:
        wide.append(
            "    {p} & {s} & {d0} -- {d1} & {n0}$\\to${n1} & {nmin}--{nmax} & "
            "{m0}$\\to${m1} & {mmin}--{mmax} & {ng}$\\times$ & {mg}$\\times$ & "
            "{dr} \\\\".format(
                p=tex_escape(r["project"]),
                s=r["snapshots"],
                d0=r["date_start"][:7],
                d1=r["date_end"][:7],
                n0=tex_int(r["nodes_first"]),
                n1=tex_int(r["nodes_last"]),
                nmin=tex_int(r["nodes_min"]),
                nmax=tex_int(r["nodes_max"]),
                m0=tex_int(r["edges_first"]),
                m1=tex_int(r["edges_last"]),
                mmin=tex_int(r["edges_min"]),
                mmax=tex_int(r["edges_max"]),
                ng=f"{r['node_growth_multiple']:.1f}",
                mg=f"{r['edge_growth_multiple']:.1f}",
                dr=r["drift_events"],
            )
        )
    wide += [
        r"    \midrule",
        "    All & {s} & {d0} -- {d1} & \\multicolumn{{4}}{{c}}"
        "{{{y} cumulative years}} & & & {dr} \\\\".format(
            s=total["snapshots"],
            d0=total["date_start"][:7],
            d1=total["date_end"][:7],
            y=f"{cumulative_years:.1f}",
            dr=total["drift_events"],
        ),
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{3pt}",
        r"  \begin{minipage}{\linewidth}\footnotesize\raggedright",
        "  " + note,
        r"  \end{minipage}",
        r"\end{table*}",
        "",
    ]

    # Same numbers transposed, for authors who need this in one column.
    metrics = [
        ("Snapshots", lambda r: str(r["snapshots"])),
        # Two rows rather than one span. A "2022-04 -- 2026-05" cell is the widest
        # thing in the table and pushes it past a single column on its own.
        ("First snapshot", lambda r: r["date_start"]),
        ("Last snapshot", lambda r: r["date_end"]),
        ("Nodes, first$\\to$last",
         lambda r: f"{tex_int(r['nodes_first'])}$\\to${tex_int(r['nodes_last'])}"),
        ("Nodes, min--max",
         lambda r: f"{tex_int(r['nodes_min'])}--{tex_int(r['nodes_max'])}"),
        ("Edges, first$\\to$last",
         lambda r: f"{tex_int(r['edges_first'])}$\\to${tex_int(r['edges_last'])}"),
        ("Edges, min--max",
         lambda r: f"{tex_int(r['edges_min'])}--{tex_int(r['edges_max'])}"),
        ("Node growth", lambda r: f"{r['node_growth_multiple']:.1f}$\\times$"),
        ("Edge growth", lambda r: f"{r['edge_growth_multiple']:.1f}$\\times$"),
        ("Drift events", lambda r: str(r["drift_events"])),
        ("Snapshot gap, med (d)", lambda r: f"{r['median_snapshot_gap_days']:.0f}"),
        ("Snapshot gap, max (d)", lambda r: f"{r['max_snapshot_gap_days']:.0f}"),
    ]
    tall = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        "% Single-column rendering of table1. Same numbers, transposed.",
        r"\begin{table}[t]",
        r"  \centering",
        r"  \footnotesize",
        *caption[:-1],
        r"  \label{tab:dataset}",
        r"  \begin{tabular}{l" + "r" * len(rows) + "}",
        r"    \toprule",
        "    & " + " & ".join(tex_escape(r["project"]) for r in rows) + r" \\",
        r"    \midrule",
    ]
    for label, get in metrics:
        tall.append("    " + label + " & " + " & ".join(get(r) for r in rows) + r" \\")
    tall += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{3pt}",
        r"  \begin{minipage}{\linewidth}\footnotesize\raggedright",
        # The corpus totals live in the wrapping note here rather than in a spanned
        # footer row, which would set the table wider than one column on its own.
        "  Corpus totals, {s} snapshots over {y} cumulative years with {dr} drift "
        "events. {note}".format(
            s=total["snapshots"],
            y=f"{cumulative_years:.1f}",
            dr=total["drift_events"],
            note=note,
        ),
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]

    written = write_table("table1_dataset_characterization", frame, "\n".join(wide))
    transposed = TAB_DIR / "table1_dataset_characterization_transposed.tex"
    transposed.write_text("\n".join(tall))
    return written + [transposed]


SCHEMA = [
    ("longitudinal_<project>.csv", "date", "ISO-8601 datetime",
     "Author timestamp of the sampled commit."),
    ("longitudinal_<project>.csv", "sha", "string (40 hex)",
     "Full git commit SHA the snapshot was extracted at."),
    ("longitudinal_<project>.csv", "commit_msg", "string",
     "Commit subject line, truncated to 120 characters."),
    ("longitudinal_<project>.csv", "N", "integer",
     "Nodes in the lineage DAG, one per resolved dbt model."),
    ("longitudinal_<project>.csv", "M", "integer",
     "Directed edges, one per ref() call between two resolved models."),
    ("longitudinal_<project>.csv", "too_small", "boolean",
     "True when N < 5 and the D1-D4 descriptors were skipped. False throughout the release."),
    ("longitudinal_<project>.csv", "D1_csi", "float [0,1]",
     "Community stability index. Fraction of consecutive steps in a 15-point Louvain "
     "resolution sweep whose partitions differ by NVI < 0.1."),
    ("longitudinal_<project>.csv", "D1_n_comm", "integer",
     "Communities found at Louvain resolution gamma = 1."),
    ("longitudinal_<project>.csv", "D2_max_gini", "float [0,1]",
     "Maximum over depth of the Gini coefficient of the blast-radius distribution."),
    ("longitudinal_<project>.csv", "D3_alg_conn", "float ≥ 0",
     "Algebraic connectivity, the second-smallest Laplacian eigenvalue of the "
     "undirected connected skeleton."),
    ("longitudinal_<project>.csv", "D3_norm_gap", "float [0,1]",
     "Algebraic connectivity divided by the largest Laplacian eigenvalue."),
    ("longitudinal_<project>.csv", "D3_fiedler_bim", "float [0,1]",
     "Bimodality coefficient of the Fiedler vector."),
    ("longitudinal_<project>.csv", "D4_cycle_rank_norm", "float ≥ 0",
     "Cycle rank (M - N + C) of the undirected skeleton, divided by N."),
    ("drift_events_refined.csv", "project", "string",
     "cal-itp or mattermost."),
    ("drift_events_refined.csv", "date", "ISO-8601 date",
     "Date of the later snapshot in the pair that produced the step change."),
    ("drift_events_refined.csv", "descriptor", "string",
     "Which descriptor drifted. One of D1_csi, D3_alg_conn, D4_cycle_rank_norm."),
    ("drift_events_refined.csv", "prev", "float",
     "Descriptor value at the preceding snapshot."),
    ("drift_events_refined.csv", "curr", "float",
     "Descriptor value at this snapshot."),
    ("drift_events_refined.csv", "pct_change", "float > 20",
     "100 * |curr - prev| / |prev|. Rows are emitted only above 20."),
    ("drift_events_refined.csv", "commit_msg", "string",
     "Commit subject line at the later snapshot."),
]


def table_schema():
    frame = pd.DataFrame(SCHEMA, columns=["file", "field", "type", "description"])

    body = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table*}[t]",
        r"  \centering",
        r"  \footnotesize",
        r"  \caption{Schema of the released longitudinal corpus. Every field in"
        r" every released file.}",
        r"  \label{tab:schema}",
        r"  \begin{tabular}{llp{0.56\linewidth}}",
        r"    \toprule",
        r"    Field & Type & Description \\",
    ]
    last_file = None
    for f, field, typ, desc in SCHEMA:
        if f != last_file:
            body.append(r"    \midrule")
            body.append(
                "    \\multicolumn{{3}}{{l}}{{\\textit{{\\texttt{{{}}}}}}} \\\\".format(
                    tex_escape(f)
                )
            )
            body.append(r"    \midrule")
            last_file = f
        body.append(
            "    \\texttt{{{}}} & {} & {} \\\\".format(
                tex_escape(field), tex_escape(typ), tex_escape(desc)
            )
        )
    body += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table*}",
        "",
    ]
    return write_table("table2_schema", frame, "\n".join(body))


def table_summary_statistics(frames, drift):
    pooled = pd.concat(
        [frames[p].assign(project=p) for p in PROJECTS], ignore_index=True
    )
    fields = [
        ("N", r"\texttt{N}"),
        ("M", r"\texttt{M}"),
        ("D1_csi", r"\texttt{D1\_csi}"),
        ("D1_n_comm", r"\texttt{D1\_n\_comm}"),
        ("D2_max_gini", r"\texttt{D2\_max\_gini}"),
        ("D3_alg_conn", r"\texttt{D3\_alg\_conn}"),
        ("D3_norm_gap", r"\texttt{D3\_norm\_gap}"),
        ("D3_fiedler_bim", r"\texttt{D3\_fiedler\_bim}"),
        ("D4_cycle_rank_norm", r"\texttt{D4\_cycle\_rank\_norm}"),
    ]

    rows = []
    for col, _ in fields:
        s = pd.to_numeric(pooled[col], errors="coerce").dropna()
        rows.append(
            {
                "field": col,
                "n": int(len(s)),
                "min": float(s.min()),
                "q25": float(s.quantile(0.25)),
                "median": float(s.median()),
                "mean": float(s.mean()),
                "q75": float(s.quantile(0.75)),
                "max": float(s.max()),
                "sd": float(s.std(ddof=1)),
            }
        )
    frame = pd.DataFrame(rows)

    gaps = pd.concat(
        [frames[p]["date"].diff().dt.days.dropna() for p in PROJECTS], ignore_index=True
    )
    corpus = {
        "projects": len(PROJECTS),
        "snapshots": int(len(pooled)),
        "cumulative_years": round(
            sum(
                (frames[p]["date"].max() - frames[p]["date"].min()).days for p in PROJECTS
            )
            / 365.25,
            3,
        ),
        "observation_window_start": pooled["date"].min().strftime("%Y-%m-%d"),
        "observation_window_end": pooled["date"].max().strftime("%Y-%m-%d"),
        "drift_events": int(len(drift)),
        "drift_threshold_pct": DRIFT_THRESHOLD_PCT,
        "descriptors_monitored_for_drift": len(DRIFT_DESCRIPTORS),
        "median_snapshot_gap_days": float(gaps.median()),
        "mean_snapshot_gap_days": round(float(gaps.mean()), 1),
        "max_snapshot_gap_days": float(gaps.max()),
    }
    corpus_frame = pd.DataFrame(
        [{"field": k, "n": "", "min": "", "q25": "", "median": v,
          "mean": "", "q75": "", "max": "", "sd": ""}
         for k, v in corpus.items()]
    )
    frame = pd.concat([corpus_frame, frame], ignore_index=True)

    counts = ("N", "M", "D1_n_comm")

    def fmt(v, col, stat):
        if col in counts:
            # Min/median/max of an integer field are integers. Mean and SD are not,
            # and rounding them to whole numbers throws away the spread.
            return f"{v:.0f}" if stat in ("min", "median", "max") else f"{v:.1f}"
        return f"{v:.3f}"

    body = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table}[t]",
        r"  \centering",
        r"  \footnotesize",
        r"  \caption{Corpus summary. Distributions pool all"
        f" {corpus['snapshots']} snapshots across both projects. Field names are"
        r" defined in Table~\ref{tab:schema}.}",
        r"  \label{tab:summary}",
        r"  \setlength{\tabcolsep}{2.5pt}",
        r"  \begin{tabular}{lrrrrr}",
        r"    \toprule",
        r"    \multicolumn{6}{l}{\textit{Corpus}} \\",
        r"    \midrule",
        f"    Projects & \\multicolumn{{5}}{{r}}{{{corpus['projects']}}} \\\\",
        f"    Snapshots & \\multicolumn{{5}}{{r}}{{{corpus['snapshots']}}} \\\\",
        f"    Cumulative years & \\multicolumn{{5}}{{r}}"
        f"{{{corpus['cumulative_years']:.1f}}} \\\\",
        f"    Observation window & \\multicolumn{{5}}{{r}}"
        f"{{{corpus['observation_window_start'][:7]} -- "
        f"{corpus['observation_window_end'][:7]}}} \\\\",
        f"    Drift events ($>${DRIFT_THRESHOLD_PCT:.0f}\\%) &"
        f" \\multicolumn{{5}}{{r}}{{{corpus['drift_events']}}} \\\\",
        f"    Snapshot gap (d) & \\multicolumn{{5}}{{r}}"
        f"{{{corpus['median_snapshot_gap_days']:.0f} median, "
        f"{corpus['max_snapshot_gap_days']:.0f} max}} \\\\",
        r"    \midrule",
        r"    \multicolumn{6}{l}{\textit{Per-snapshot fields}} \\",
        r"    \midrule",
        r"    Field & Min & Median & Mean & Max & SD \\",
        r"    \midrule",
    ]
    for (col, label), r in zip(fields, rows):
        body.append(
            "    {lab} & {mn} & {md} & {mu} & {mx} & {sd} \\\\".format(
                lab=label,
                mn=fmt(r["min"], col, "min"),
                md=fmt(r["median"], col, "median"),
                mu=fmt(r["mean"], col, "mean"),
                mx=fmt(r["max"], col, "max"),
                sd=fmt(r["sd"], col, "sd"),
            )
        )
    body += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
    ]
    return write_table("table3_summary_statistics", frame, "\n".join(body))


# --------------------------------------------------------------------------

def main():
    set_style()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TAB_DIR.mkdir(parents=True, exist_ok=True)

    frames = load_longitudinal()
    drift = load_drift(frames)
    print(
        f"Loaded {sum(len(f) for f in frames.values())} snapshots across "
        f"{len(frames)} projects, {len(drift)} drift events reproduced from source."
    )

    written = []
    written += fig_growth_trajectories(frames, drift)
    written += fig_density_evolution(frames)
    written += fig_drift_characterization(drift)
    written += fig_snapshot_cadence(frames)
    written += fig_descriptor_trajectories(frames)
    written += table_dataset_characterization(frames, drift)
    written += table_schema()
    written += table_summary_statistics(frames, drift)

    print(f"\nWrote {len(written)} files:")
    for path in written:
        print(f"  {path.relative_to(REPO_ROOT)}")

    print("\nNot produced, the release cannot support them:")
    for name, reason in DROPPED_FIGURES:
        print(f"  - {name}\n      {reason}")

    # summary_refined.json disagrees with the CSVs it summarises. Surface it every
    # run rather than letting a stale number reach the paper.
    for project, claimed in [("cal-itp", (74, 562)), ("mattermost", (197, 235))]:
        df = frames[project]
        actual = (int(df["N"].iloc[0]), int(df["N"].iloc[-1]))
        if actual != claimed:
            print(
                f"\nWARNING artifacts/phase_4/summary_refined.json claims {project} "
                f"N_growth {claimed[0]} -> {claimed[1]} "
                f"({claimed[1] / claimed[0]:.1f}x); the CSV is "
                f"{actual[0]} -> {actual[1]} ({actual[1] / actual[0]:.1f}x)."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
