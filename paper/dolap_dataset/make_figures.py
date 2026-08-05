"""Regenerate every figure and table for the MSR longitudinal-lineage dataset paper.

Reads a corpus directory of per-project snapshot CSVs and writes figures (PDF +
PNG) and tables (CSV + booktabs LaTeX). Nothing about the project list is
hardcoded. The script discovers whatever ``longitudinal_*.csv`` files the corpus
directory holds and lays every per-project figure out as small multiples, so the
same code renders two projects today and hundreds after the wider extraction
lands. Per-project grids cap at MAX_PANELS; corpus-level figures use every project.

Run:

    PYTHONPATH=src /usr/bin/python3 paper/dolap_dataset/make_figures.py
    PYTHONPATH=src /usr/bin/python3 paper/dolap_dataset/make_figures.py \
        --corpus artifacts/phase_6_corpus

Figures are sized for IEEEtran ``conference``, whose column is 252.0pt and whose
text block is 516.0pt, both measured from the class rather than assumed.

No step here is stochastic. ``SEED`` is set so that adding a resampled panel
later cannot silently break reproducibility.

D1 IS EXCLUDED. See EXCLUDED_FIELDS. The lineage extractor seeds each graph from
a Python set, so node insertion order follows PYTHONHASHSEED, and Louvain is
order-sensitive. Every D1 figure, table row and drift event is dropped. D2, D3
and D4 are order-stable and are kept.
"""
import argparse
import json
import math
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
from scipy.stats import spearmanr

SEED = 42
np.random.seed(SEED)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
DEFAULT_CORPUS = REPO_ROOT / "artifacts" / "phase_4"

# IEEEtran conference, measured: \columnwidth 252.0pt, \textwidth 516.0pt.
# A LaTeX point is 1/72.27in; matplotlib inches are 1/72in, so convert.
LATEX_PT_PER_IN = 72.27
COL_W = 252.0 / LATEX_PT_PER_IN
FULL_W = 516.0 / LATEX_PT_PER_IN

# Okabe-Ito. Colourblind-safe. Metric identity carries the colour; project
# identity carries the panel position, which is what lets the layout scale.
METRIC_COLOR = {"N": "#0072B2", "M": "#D55E00"}
METRIC_STYLE = {"N": "-", "M": "--"}
SERIES_PALETTE = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7",
    "#E69F00", "#56B4E9", "#666666", "#F0E442",
]
MUTED = "#999999"
ACCENT = "#0072B2"

STRUCTURAL_COLUMNS = (
    "date", "sha", "commit_msg", "too_small", "N", "M",
    # Connectivity and provenance fields the corpus extractor emits. These
    # describe the graph rather than measure it, so they must not appear as
    # descriptor panels or sit beside D2/D3/D4 in the summary table.
    "n_components", "giant_component_frac", "isolated_frac",
    "n_sql_files", "n_dbt_projects",
)
REQUIRED_COLUMNS = ("date", "N", "M")

# D1 and D3 are computed on the largest weakly connected component, not the whole
# graph. The primary correction for that is the axis label, not the population:
# every gated descriptor is labelled LWCC so a reader is never invited to compare
# a subgraph statistic against a whole-graph N. The floor is then doing much less
# work, which is the right amount for a threshold the data cannot justify. On
# this corpus median giant_component_frac is 0.522, spread near-uniformly from
# 0.003 to 1.0 with no natural cut, so 0.9 would have excluded 82% of projects.
# 0.5 is adopted because it is the connectivity cut the release already uses
# inside its own core definition, so the paper carries one documented threshold
# rather than a second one invented here.
MIN_GIANT_COMPONENT_FRAC = 0.5
LWCC_SUFFIX = "LWCC"
GIANT_COMPONENT_COLUMN = "giant_component_frac"
GIANT_COMPONENT_PREFIXES = ("D1_", "D3_")

DRIFT_THRESHOLD_PCT = 20.0
SAMPLING_WINDOW_DAYS = 30
MIN_SNAPSHOTS = 4
# Below this many projects a quantile band over per-project curves is noise.
BAND_MIN_PROJECTS = 5
# Above this the per-project legend and coloured overlay lines are dropped.
LEGEND_MAX_PROJECTS = 6
# Small multiples stop working long before the corpus does. At 303 projects an
# uncapped grid renders a 41-inch-tall figure, so the per-project grids show the
# largest MAX_PANELS and say how many they left out. Corpus-level figures still
# use every project.
MAX_PANELS = 24

# Fields that exist in the release but must not be plotted or summarised.
EXCLUDED_FIELDS = {
    "D1_csi": (
        "Nondeterministic. extract_lineage_at_commit seeds the graph from a Python "
        "set, so node insertion order follows PYTHONHASHSEED, and Louvain is "
        "order-sensitive. Across eight node orderings of one fixed 223-node graph "
        "the value took four distinct values spanning 0.714 to 0.929, a swing of "
        "0.214 against a corpus SD of 0.123."
    ),
    "D1_n_comm": (
        "Nondeterministic, same cause. The same fixed graph yielded 9 or 10 "
        "communities depending on node insertion order."
    ),
}

# Descriptors the published step-change method monitors, minus D1. D3_norm_gap and
# D2_max_gini are deliberately not added: norm_gap sits at 1e-3 and below, where a
# relative-change threshold is meaningless.
DEFAULT_DRIFT_DESCRIPTORS = ["D3_alg_conn", "D4_cycle_rank_norm"]

FIELD_DOCS = {
    "date": ("ISO-8601 datetime", "Author timestamp of the sampled commit."),
    "sha": ("string (40 hex)", "Full git commit SHA the snapshot was extracted at."),
    "commit_msg": ("string", "Commit subject line, truncated to 120 characters."),
    "N": ("integer", "Nodes in the lineage DAG, one per resolved dbt model."),
    "M": ("integer", "Directed edges, one per ref() call between two resolved models."),
    "too_small": ("boolean", "True when N is below 5 and the descriptors were skipped."),
    "D1_csi": ("float [0,1]", "Community stability index over a Louvain resolution sweep, on the largest "
        "weakly connected component. Excluded, see note below."),
    "D1_n_comm": ("integer", "Louvain communities at gamma 1, on the largest weakly connected component. "
        "Excluded, see note below."),
    "D2_max_gini": (
        "float [0,1]",
        "Maximum over depth of the Gini coefficient of the blast-radius distribution.",
    ),
    "D3_alg_conn": (
        "float ≥ 0",
        "Algebraic connectivity, the second-smallest Laplacian eigenvalue, on the "
        "largest weakly connected component. Not on all N nodes.",
    ),
    "D3_norm_gap": (
        "float [0,1]",
        "Algebraic connectivity divided by the largest Laplacian eigenvalue, on "
        "the largest weakly connected component.",
    ),
    "D3_fiedler_bim": (
        "float [0,1]",
        "Bimodality coefficient of the Fiedler vector, on the largest weakly "
        "connected component. Order-stable to 5e-6 relative, five orders below "
        "its corpus SD, and the one descriptor the release does not measure.",
    ),
    "giant_component_frac": (
        "float (0,1]",
        "Share of N in the largest weakly connected component. The covariate for "
        "every LWCC descriptor: where it is small, those descriptors describe a "
        "fraction of the project.",
    ),
    "n_components": ("integer", "Weakly connected components in the lineage DAG."),
    "isolated_frac": ("float [0,1]", "Share of N with no lineage edge at all."),
    "n_sql_files": ("integer", "Model .sql files found at the sampled commit."),
    "n_dbt_projects": ("integer", "dbt_project.yml files found at the sampled commit."),
    "project_id": ("string", "GitHub owner and repo joined by a double underscore."),
    "D4_cycle_rank_norm": (
        "float ≥ 0",
        "Cycle rank (M - N + C) of the undirected skeleton, divided by N.",
    ),
}

# Column contracts for the figures the current corpus cannot support. The
# extraction that lands next only has to emit one of these shapes for the figure
# to appear, and the skip message states the contract verbatim.
LAYER_PREFIX = "layer_"
# A dbt source is declared in YAML and is not a model, so a count over model
# files correctly has no source bucket. n_unclassified is the honest remainder
# and dropping it renormalises the stack to a total that excludes real models.
LAYER_COUNT_COLUMNS = ("n_staging", "n_intermediate", "n_mart", "n_unclassified")
COVERAGE_COLUMNS = {
    "doc_rate": ("doc_rate", "documentation_coverage", "documented_frac"),
    "test_rate": ("test_rate", "test_coverage", "tested_frac"),
}
DEGREE_SUBDIR = "degrees"


# --------------------------------------------------------------------------
# Corpus discovery and validation
# --------------------------------------------------------------------------

def discover_projects(corpus_dir):
    """Return ({project: DataFrame}, skipped) for every longitudinal_*.csv found."""
    paths = sorted(corpus_dir.glob("longitudinal_*.csv"))
    if not paths:
        raise SystemExit(
            f"No longitudinal_*.csv under {corpus_dir}. Point --corpus at the "
            f"directory the extraction writes."
        )
    frames, skipped, dropped_snapshots = {}, [], []
    for path in paths:
        project = path.stem[len("longitudinal_"):]
        df = pd.read_csv(path)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            skipped.append((project, f"missing required column(s) {missing}"))
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        if len(df) < MIN_SNAPSHOTS:
            skipped.append((project, f"{len(df)} snapshots, need {MIN_SNAPSHOTS}"))
            continue
        if df[["N", "M"]].isna().any().any():
            skipped.append((project, "missing N or M"))
            continue
        degenerate = int((df["N"] <= 1).sum())
        if degenerate:
            # A one-node snapshot has no graph to describe and an undefined
            # density. Drop those rows, not the project: on this corpus the
            # whole-project rule discarded 180 snapshots to avoid 9 bad values.
            df = df[df["N"] > 1].reset_index(drop=True)
            dropped_snapshots.append((project, degenerate))
            if len(df) < MIN_SNAPSHOTS:
                skipped.append(
                    (project, f"{len(df)} snapshots left after dropping "
                              f"{degenerate} with N <= 1")
                )
                continue
        frames[project] = df
    if not frames:
        raise SystemExit(f"Every project under {corpus_dir} was skipped: {skipped}")
    # Largest first, so the small-multiples grid reads in a meaningful order.
    ordered = sorted(frames, key=lambda p: (-len(frames[p]), p))
    if dropped_snapshots:
        total = sum(n for _, n in dropped_snapshots)
        print(f"  dropped {total} degenerate snapshot(s) with N <= 1 across "
              f"{len(dropped_snapshots)} project(s), projects retained")
    return {p: frames[p] for p in ordered}, skipped


def load_tiers(corpus_dir):
    """{project_id: tier} from the released corpus_index.csv, or {} if absent.

    Looked for beside the longitudinal files and one level up, since --corpus
    points at <release>/longitudinal/ while the index sits at <release>/.
    """
    for candidate in (corpus_dir / "corpus_index.csv",
                      corpus_dir.parent / "corpus_index.csv"):
        if candidate.is_file():
            idx = pd.read_csv(candidate)
            if {"project_id", "tier"} <= set(idx.columns):
                return dict(zip(idx["project_id"], idx["tier"])), candidate
    return {}, None


def label_of(project):
    """Display label. Known slugs keep their capitalisation.

    Corpus project ids are `owner__repo`, so the separator is rendered as a
    slash rather than collapsed into whitespace.
    """
    special = {"cal-itp": "Cal-ITP", "mattermost": "Mattermost"}
    if project in special:
        return special[project]
    if "__" in project:
        owner, _, repo = project.partition("__")
        return f"{owner}/{repo}"
    return project.replace("_", " ")


def elide(text, max_chars):
    """Shorten by removing the middle, so the distinguishing suffix survives."""
    if len(text) <= max_chars:
        return text
    keep = max_chars - 1
    return text[: keep // 2] + "\u2026" + text[-(keep - keep // 2):]


def panel_labels(projects, max_chars=17):
    """Short titles for small-multiple panels.

    Full owner/repo does not fit a 1.15in panel and the titles collide. Use the
    repo alone where that is unambiguous across the corpus, fall back to
    owner/repo where two owners ship the same repo name, and elide the middle
    rather than the tail so a truncated name keeps its distinguishing suffix.
    """
    repos = {}
    for project in projects:
        repo = project.partition("__")[2] if "__" in project else project
        repos.setdefault(repo, []).append(project)
    out = {}
    for project in projects:
        repo = project.partition("__")[2] if "__" in project else project
        text = label_of(project) if len(repos[repo]) > 1 else repo
        out[project] = elide(text, max_chars)
    return out


def descriptor_fields(frames, also_exclude=()):
    """Numeric non-structural columns present in every project, minus exclusions.

    Layer and coverage columns are excluded because they have their own figures;
    they are still summarised in Table 3.
    """
    drop = set(also_exclude)
    common = None
    for df in frames.values():
        cols = {
            c for c in df.columns
            if c not in STRUCTURAL_COLUMNS
            and c not in EXCLUDED_FIELDS
            and c not in drop
            and not c.startswith(LAYER_PREFIX)
            and not c.startswith(tuple(LAYER_COUNT_COLUMNS))
            and pd.api.types.is_numeric_dtype(df[c])
        }
        common = cols if common is None else (common & cols)
    return sorted(common or [])


def compute_drift(frames, descriptors, eligible=None):
    """Step changes above the threshold between consecutive snapshots.

    A step change in a giant-component descriptor is only meaningful where the
    descriptor is, so projects outside `eligible` contribute no events for D1 or
    D3. They still contribute events for whole-graph descriptors.
    """
    rows = []
    for project, df in frames.items():
        for desc in descriptors:
            if desc not in df.columns:
                continue
            if (eligible is not None and is_component_gated(desc)
                    and project not in eligible):
                continue
            s = pd.to_numeric(df[desc], errors="coerce")
            pct = (s.diff().abs() / s.shift(1).abs()) * 100.0
            for i in pct.index[pct > DRIFT_THRESHOLD_PCT]:
                rows.append(
                    {
                        "project": project,
                        "date": df["date"].iloc[i],
                        "descriptor": desc,
                        "prev": s.iloc[i - 1],
                        "curr": s.iloc[i],
                        "pct_change": pct.iloc[i],
                    }
                )
    return pd.DataFrame(
        rows, columns=["project", "date", "descriptor", "prev", "curr", "pct_change"]
    )


def drift_dates(drift, project):
    if drift.empty:
        return np.array([], dtype="datetime64[ns]")
    return np.sort(drift.loc[drift["project"] == project, "date"].unique())


def layer_columns(frames):
    """Layer-composition columns if the corpus carries them, else [].

    Refuses to return a partial set. A stacked composition renormalised over
    a subset of the layers asserts that the omitted layers are empty, which is
    a fabricated claim rather than a missing one, so an incomplete set is
    dropped with a printed reason instead of rendered.
    """
    df = next(iter(frames.values()))
    prefixed = sorted(c for c in df.columns if c.startswith(LAYER_PREFIX))
    counts = [c for c in LAYER_COUNT_COLUMNS if c in df.columns]
    cols = prefixed if len(prefixed) >= 2 else counts
    if len(cols) < 2:
        return []

    # Every model lands in exactly one bucket, so the buckets must account for N.
    # If they do not, a layer is missing and stacking the rest would redistribute
    # the shortfall across them, asserting that the missing layer is empty. Both
    # the layer_ and the n_ contract are checked, not just one of them.
    for project, frame in frames.items():
        absent = sorted(set(cols) - set(frame.columns))
        if absent:
            print(f"  layer: skipped, {project} lacks {absent}")
            return []
        shortfall = (frame["N"] - frame[list(cols)].sum(axis=1)).abs()
        worst = float(shortfall.max()) if len(shortfall) else 0.0
        if worst > 0:
            print(
                f"  layer: skipped, buckets {cols} do not account for every model "
                f"in {project}. Worst snapshot is off by {worst:.0f} against "
                f"N={int(frame['N'].max())}. Add the missing layer column rather "
                f"than renormalising over a subset."
            )
            return []
    return cols


def coverage_columns(frames):
    """{canonical: actual} for coverage columns the corpus carries."""
    df = next(iter(frames.values()))
    found = {}
    for canonical, candidates in COVERAGE_COLUMNS.items():
        for candidate in candidates:
            if candidate in df.columns:
                found[canonical] = candidate
                break
    return found


def degree_files(corpus_dir, frames):
    """{project: path} for per-node degree files, if the corpus ships them."""
    d = corpus_dir / DEGREE_SUBDIR
    if not d.is_dir():
        return {}
    return {p: d / f"{p}.csv" for p in frames if (d / f"{p}.csv").is_file()}


# --------------------------------------------------------------------------
# Style and layout
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
            "lines.markersize": 2.2,
            "grid.linewidth": 0.4,
            "grid.alpha": 0.30,
            "grid.color": MUTED,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            # Type 42 keeps fonts TrueType. Type 3 fails IEEE and ACM PDF checks.
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def capped(frames, max_panels):
    """(subset, omitted) keeping the largest projects. frames is already sorted."""
    if max_panels is None or len(frames) <= max_panels:
        return frames, 0
    keep = list(frames)[:max_panels]
    return {p: frames[p] for p in keep}, len(frames) - max_panels


def omitted_note(omitted, total):
    return (
        f"{total - omitted} largest of {total} projects, "
        f"{omitted} not shown" if omitted else None
    )


def grid_layout(n, panel_h_small=1.15, panel_h_large=0.80):
    """(nrows, ncols, figsize) for n small multiples.

    Up to three panels this stays a single-column stack. Past that it moves to the
    full text block and widens the grid, so fifty projects render as a readable
    six-across sheet instead of fifty overplotted lines.
    """
    if n <= 3:
        return n, 1, (COL_W, n * panel_h_small + 0.45)
    ncols = min(6, max(2, math.ceil(math.sqrt(n * 1.4))))
    nrows = math.ceil(n / ncols)
    panel_h = panel_h_small if n <= 8 else panel_h_large
    return nrows, ncols, (FULL_W, nrows * panel_h + 0.45)


def year_axis(ax, compact=False):
    """Year ticks, thinned so a 0.8in-wide panel does not collide with itself."""
    span_years = max(1.0, float(np.ptp(ax.get_xlim())) / 365.25)
    every = max(1, math.ceil(span_years / (2 if compact else 6)))
    ax.xaxis.set_major_locator(mdates.YearLocator(every))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("'%y" if compact else "%Y"))


def plain_log_ticks(axis, ticks):
    """Plain numbers on a log axis. The default 10^k labels leave most of these
    ranges with a single tick."""
    axis.set_major_locator(FixedLocator(ticks))
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    axis.set_minor_formatter(NullFormatter())


def panel_tag(ax, tag):
    ax.text(
        -0.17, 1.04, tag, transform=ax.transAxes,
        fontsize=8, fontweight="bold", va="bottom", ha="left",
    )


def blank_unused(axes_flat, used):
    for ax in axes_flat[used:]:
        ax.axis("off")


def grid_legend(fig, flat, used, handles, labels, xlabel, figsize, ncol=3):
    """Put a shared legend in the first spare grid cell, or below the grid.

    When the projects exactly fill the grid there is no spare cell, and a legend
    anchored at the default offset lands on top of the shared x-label. The offset
    below is expressed as a fraction of this figure's height so the clearance
    holds whatever the grid size.
    """
    fig.supxlabel(xlabel, fontsize=8, y=-0.01)
    if used < len(flat):
        flat[used].legend(handles, labels, loc="center", handlelength=1.8)
    else:
        clearance = 0.34 / figsize[1]
        fig.legend(
            handles, labels, loc="lower center", ncol=ncol,
            bbox_to_anchor=(0.5, -0.01 - clearance), handlelength=1.8,
        )


def ecdf(values):
    """Step coordinates for an empirical CDF, anchored at y=0."""
    x = np.sort(np.asarray(values, dtype=float))
    if len(x) == 0:
        return np.array([]), np.array([])
    y = np.arange(1, len(x) + 1) / len(x)
    return np.concatenate([x[:1], x]), np.concatenate([[0.0], y])


def median_band(ax, curves, color="#000000", label="corpus median, IQR"):
    """Median and interquartile band over per-project curves.

    curves is a list of (x, y). Below BAND_MIN_PROJECTS the quantiles are noise
    and nothing is drawn.

    The grid runs to the median series end, and each series contributes only
    where it has data. Intersecting the series ranges instead, which is the
    obvious approach, collapses at corpus scale: with 121 projects the shortest
    one truncates the common window to nothing and no band renders at all.
    """
    if len(curves) < BAND_MIN_PROJECTS:
        return False
    ends = np.array([float(x.max()) for x, _ in curves])
    lo = float(min(float(x.min()) for x, _ in curves))
    hi = float(np.median(ends))
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return False
    grid = np.linspace(lo, hi, 120)
    stack = np.full((len(curves), grid.size), np.nan)
    for i, (x, y) in enumerate(curves):
        inside = (grid >= x.min()) & (grid <= x.max())
        stack[i, inside] = np.interp(grid[inside], x, y)
    # Only report a quantile where enough series are actually present.
    enough = np.count_nonzero(~np.isnan(stack), axis=0) >= BAND_MIN_PROJECTS
    if not enough.any():
        return False
    grid, stack = grid[enough], stack[:, enough]
    q25, q50, q75 = np.nanpercentile(stack, [25, 50, 75], axis=0)
    ax.fill_between(grid, q25, q75, color=color, alpha=0.15, linewidth=0)
    ax.plot(grid, q50, color=color, linewidth=1.3, label=label)
    return True


def wrapped_supxlabel(fig, text, width_in, fontsize=6.5, y=-0.03):
    """Shared caption wrapped to the figure width.

    matplotlib does not wrap supxlabel, and with bbox_inches tight a long single
    line widens the saved figure past the text block it has to fit inside.
    """
    # 0.62em per character is a safe average for this serif at small sizes;
    # 0.5 underestimates and the wrapped block still overhangs the text block.
    chars = max(40, int(width_in * 72 / (fontsize * 0.62)))
    fig.supxlabel("\n".join(textwrap.wrap(text, chars)), fontsize=fontsize, y=y)


def save(fig, stem, fig_dir):
    pdf = fig_dir / f"{stem}.pdf"
    png = fig_dir / f"{stem}.png"
    fig.savefig(pdf)
    fig.savefig(png, dpi=300)
    plt.close(fig)
    return [pdf, png]


def relative_years(df):
    return (df["date"] - df["date"].iloc[0]).dt.days.values / 365.25


def growth_multiple(series):
    """Last over first, or NaN when the first value is zero.

    A project whose first snapshot has no edges has an undefined multiple, not
    an infinite one, and feeding inf into a median or an axis is worse than a gap.
    """
    first, last = float(series.iloc[0]), float(series.iloc[-1])
    return last / first if first > 0 else float("nan")


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def fig_growth_trajectories(frames, drift, fig_dir, max_panels=MAX_PANELS):
    """Anchor figure. Nodes and edges per project as small multiples.

    Project identity is carried by panel position, not colour, which is what
    keeps this readable as the corpus grows. Past max_panels the grid shows the
    largest projects only; fig2 carries the whole population.
    """
    total = len(frames)
    frames, omitted = capped(frames, max_panels)
    n = len(frames)
    nrows, ncols, figsize = grid_layout(n)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    flat = axes.ravel()
    compact = n > 3
    titles = panel_labels(list(frames))

    for ax, (project, df) in zip(flat, frames.items()):
        for col in ("N", "M"):
            ax.plot(
                df["date"], df[col],
                METRIC_STYLE[col], color=METRIC_COLOR[col], linewidth=1.0,
            )
        top = max(df["N"].max(), df["M"].max())
        ax.set_ylim(-0.18 * top, 1.08 * top)
        ax.set_yticks([t for t in ax.get_yticks() if 0 <= t <= top])
        ax.grid(axis="y")
        ax.tick_params(labelsize=6 if compact else 7)
        ax.set_title(
            f"{titles[project]} ($n$={len(df)})",
            fontsize=6.2 if compact else 8, pad=2.5,
        )
        # Drift events as a rug in the gutter reserved below zero.
        dates = drift_dates(drift, project)
        if len(dates):
            ax.vlines(
                dates, 0.02, 0.10, transform=ax.get_xaxis_transform(),
                color="#444444", linewidth=0.6,
            )
        year_axis(ax, compact=compact)

    blank_unused(flat, n)
    handles = [
        plt.Line2D([], [], color=METRIC_COLOR["N"], linestyle=METRIC_STYLE["N"]),
        plt.Line2D([], [], color=METRIC_COLOR["M"], linestyle=METRIC_STYLE["M"]),
        plt.Line2D([], [], color="#444444", linewidth=0.6),
    ]
    labels = ["nodes $N$", "edges $M$", f"drift event ({len(drift)})"]
    note = omitted_note(omitted, total)
    if note:
        labels[-1] = f"drift event"
        handles.append(plt.Line2D([], [], color="none"))
        labels.append(note)
    grid_legend(fig, flat, n, handles, labels, "Snapshot date", figsize)
    fig.tight_layout(pad=0.3, h_pad=0.7, w_pad=0.6)
    return save(fig, "fig1_growth_trajectories", fig_dir)


def fig_growth_normalized(frames, fig_dir):
    """Corpus-level view. Every project on a common relative-time axis.

    Small multiples show shape per project; this shows whether the corpus grows
    as a whole. It stays readable at any project count because individual lines
    fade to grey behind a median and an interquartile band.
    """
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.6), sharex=True)
    n = len(frames)
    thin = n > LEGEND_MAX_PROJECTS

    for idx, (metric, ax) in enumerate(zip(("N", "M"), axes)):
        curves = []
        for i, (project, df) in enumerate(frames.items()):
            years = relative_years(df)
            base = float(df[metric].iloc[0])
            if base <= 0:
                continue
            rel = df[metric].values / base
            curves.append((years, rel))
            ax.plot(
                years, rel,
                color=MUTED if thin else SERIES_PALETTE[i % len(SERIES_PALETTE)],
                linewidth=0.6 if thin else 1.0,
                alpha=0.45 if thin else 1.0,
                label=None if thin else label_of(project),
            )
        median_band(ax, curves)
        ax.axhline(1.0, color=MUTED, linewidth=0.6, linestyle=":")
        ax.set_yscale("log")
        plain_log_ticks(ax.yaxis, [0.5, 1, 2, 5, 10, 20])
        ax.set_ylabel(f"${metric}(t)\\,/\\,{metric}(0)$")
        ax.grid(axis="y")
        if idx == 0:
            ax.legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)

    axes[1].set_xlabel("Years since first snapshot")
    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    fig.align_ylabels(axes)
    fig.tight_layout(pad=0.3)
    return save(fig, "fig2_growth_normalized", fig_dir)


def fig_drift_characterization(drift, frames, descriptors, fig_dir):
    """Magnitude by descriptor and inter-arrival time, both as ECDFs.

    Recomputed from the snapshots over D1-free descriptors. Not the released
    drift_events_refined.csv, 27 of whose 44 events are D1_csi.
    """
    if drift.empty:
        return []
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.9))

    ax = axes[0]
    for i, desc in enumerate(descriptors):
        vals = drift.loc[drift["descriptor"] == desc, "pct_change"].values
        if len(vals) == 0:
            continue
        x, y = ecdf(vals)
        ax.step(
            x, y, where="post", color=SERIES_PALETTE[i % len(SERIES_PALETTE)],
            label=f"{desc.replace('_', ' ')} ($n$={len(vals)})",
        )
    ax.axvline(DRIFT_THRESHOLD_PCT, color=MUTED, linewidth=0.6, linestyle=":")
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
    pooled, per_project = [], []
    for project in frames:
        dates = drift_dates(drift, project)
        if len(dates) < 2:
            continue
        gaps = np.diff(dates).astype("timedelta64[D]").astype(float)
        pooled.extend(gaps.tolist())
        per_project.append((project, gaps))
    if pooled:
        if len(per_project) <= LEGEND_MAX_PROJECTS:
            for i, (project, gaps) in enumerate(per_project):
                x, y = ecdf(gaps)
                ax.step(
                    x, y, where="post",
                    color=SERIES_PALETTE[i % len(SERIES_PALETTE)], linewidth=0.9,
                    label=f"{label_of(project)} ($n$={len(gaps)})",
                )
        else:
            for _, gaps in per_project:
                x, y = ecdf(gaps)
                ax.step(x, y, where="post", color=MUTED, linewidth=0.5, alpha=0.4)
            ax.plot(
                [], [], color=MUTED, linewidth=0.5,
                label=f"per project ({len(per_project)})",
            )
        x, y = ecdf(pooled)
        ax.step(
            x, y, where="post", color="#000000", linewidth=1.3,
            label=f"corpus ($n$={len(pooled)})",
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
    return save(fig, "fig5_drift_characterization", fig_dir)


def fig_snapshot_cadence(frames, fig_dir, max_panels=MAX_PANELS):
    """Where snapshots fall, and how far apart they are.

    Sampling is one commit per 30-day window of commits touching the models path.
    A window with no such commit yields no snapshot, so the series is not evenly
    spaced and the gaps are the honest limitation.

    Panel (a) shows the largest max_panels projects, because a 303-row strip is
    an illegible smear. Panel (b) pools every project in the corpus.
    """
    all_frames = frames
    total = len(frames)
    frames, omitted = capped(frames, max_panels)
    n = len(frames)
    wide = n > 6
    row_h = 0.24 if n <= 8 else 0.16
    timeline_h = min(6.0, max(0.9, n * row_h))
    fig, axes = plt.subplots(
        2, 1,
        figsize=(FULL_W if wide else COL_W, timeline_h + 2.1),
        gridspec_kw={"height_ratios": [timeline_h, 1.9]},
    )

    ax = axes[0]
    order = list(reversed(list(frames)))
    for row, project in enumerate(order):
        ax.vlines(
            frames[project]["date"], row - 0.34, row + 0.34,
            color=ACCENT, linewidth=0.6,
        )
    ax.set_yticks(range(n))
    ax.set_yticklabels(
        [f"{label_of(p)} ({len(frames[p])})" for p in order],
        fontsize=5.0 if n > 24 else 6.5,
    )
    ax.set_ylim(-0.7, n - 0.3)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    year_axis(ax)
    ax.set_xlabel("Snapshot date", labelpad=1)
    note = omitted_note(omitted, total)
    if note:
        # Left-aligned inside the axes. As a centred title it collided with the
        # worst-gap annotation, which is also placed along the top.
        ax.text(0.0, 1.01, note, transform=ax.transAxes, fontsize=6.5,
                color="#333333", ha="left", va="bottom")

    worst_project, worst_gap, worst_at = None, -1.0, None
    for project, df in frames.items():
        g = df["date"].diff().dt.days
        if g.max() > worst_gap:
            i = int(g.idxmax())
            worst_gap = float(g.max())
            worst_at = df["date"].iloc[i - 1] + (df["date"].iloc[i] - df["date"].iloc[i - 1]) / 2
            worst_project = project
    if worst_project is not None:
        ax.annotate(
            f"{worst_gap:.0f}-day gap",
            xy=(worst_at, order.index(worst_project) + 0.34),
            xytext=(0, 6), textcoords="offset points",
            fontsize=6, color="#333333", ha="center",
            arrowprops=dict(arrowstyle="-", linewidth=0.5, color="#333333"),
        )

    # Panel (b) pools every project, including any the timeline above omitted.
    ax = axes[1]
    pooled = []
    for i, (project, df) in enumerate(all_frames.items()):
        gaps = df["date"].diff().dt.days.dropna().values
        pooled.extend(gaps.tolist())
        x, y = ecdf(gaps)
        if total <= LEGEND_MAX_PROJECTS:
            ax.step(
                x, y, where="post", color=SERIES_PALETTE[i % len(SERIES_PALETTE)],
                linewidth=0.9,
                label=f"{label_of(project)} (med {np.median(gaps):.0f} d)",
            )
        else:
            ax.step(x, y, where="post", color=MUTED, linewidth=0.5, alpha=0.25)
    if total > LEGEND_MAX_PROJECTS:
        ax.plot([], [], color=MUTED, linewidth=0.5, label=f"per project ({total})")
    x, y = ecdf(pooled)
    ax.step(
        x, y, where="post", color="#000000", linewidth=1.3,
        label=f"corpus (med {np.median(pooled):.0f} d)",
    )
    ax.axvline(SAMPLING_WINDOW_DAYS, color=MUTED, linewidth=0.6, linestyle=":")
    ax.text(
        SAMPLING_WINDOW_DAYS, 1.02, "30-day target",
        fontsize=6, color="#666666", ha="left", va="bottom",
    )
    ax.set_xlabel("Days between consecutive snapshots")
    ax.set_ylabel("ECDF")
    ax.set_ylim(0, 1.0)
    # Gaps span 2 days to 1686. On a linear axis the whole distribution collapses
    # against the left edge to make room for one outlier.
    if max(pooled) / max(1.0, min(pooled)) > 30:
        ax.set_xscale("log")
        plain_log_ticks(ax.xaxis, [3, 10, 30, 100, 300, 1000])
    ax.grid(axis="y")
    ax.legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)

    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    fig.tight_layout(pad=0.3, h_pad=0.6)
    # The timeline's y-tick labels are wider than "ECDF", so tight_layout leaves
    # the panels on different left edges. Snap them to a common plot box.
    boxes = [a.get_position() for a in axes]
    left, right = max(b.x0 for b in boxes), min(b.x1 for b in boxes)
    for a, b in zip(axes, boxes):
        a.set_position([left, b.y0, right - left, b.height])
    return save(fig, "fig6_snapshot_cadence", fig_dir)


def fig_density_evolution(frames, fig_dir):
    """Substitute for a degree distribution when per-node degrees are absent.

    Mean degree M/N and DAG edge density. Both are exact functions of the
    released N and M. Neither is a degree distribution.
    """
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.5), sharex=True)
    n = len(frames)
    thin = n > LEGEND_MAX_PROJECTS
    curves_mean, curves_dens = [], []

    for i, (project, df) in enumerate(frames.items()):
        years = relative_years(df)
        nn = df["N"].astype(float).values
        mm = df["M"].astype(float).values
        mean_deg = mm / nn
        density = mm / (nn * (nn - 1))
        curves_mean.append((years, mean_deg))
        curves_dens.append((years, density))
        style = dict(
            color=MUTED if thin else SERIES_PALETTE[i % len(SERIES_PALETTE)],
            linewidth=0.6 if thin else 1.0,
            alpha=0.45 if thin else 1.0,
        )
        axes[0].plot(years, mean_deg, label=None if thin else label_of(project), **style)
        axes[1].plot(years, density, **style)

    median_band(axes[0], curves_mean)
    median_band(axes[1], curves_dens, label=None)
    axes[0].set_ylabel("Mean degree $M/N$")
    axes[1].set_ylabel(r"Density $\frac{M}{N(N-1)}$")
    axes[1].set_yscale("log")
    plain_log_ticks(axes[1].yaxis, [0.002, 0.005, 0.01, 0.02, 0.05])
    for ax in axes:
        ax.grid(axis="y")
    axes[0].set_ylim(bottom=0)
    axes[1].set_xlabel("Years since first snapshot")
    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    axes[0].legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)
    fig.align_ylabels(axes)
    fig.tight_layout(pad=0.3)
    return save(fig, "figA_density_evolution", fig_dir)


def is_component_gated(descriptor):
    """True for descriptors computed on the giant component rather than the graph."""
    return descriptor.startswith(GIANT_COMPONENT_PREFIXES)


def tier_eligible(frames, tiers, keep="core"):
    """({project: df}, excluded) using the release's own tier definition.

    Preferred over an invented threshold. `core` already encodes a median giant
    component of at least half of N, alongside a snapshot-count and size floor,
    so one documented rule from the release replaces two competing knobs.
    """
    kept, excluded = {}, []
    for project, df in frames.items():
        if tiers.get(project, keep) == keep:
            kept[project] = df
        else:
            excluded.append(project)
    return kept, excluded


def component_eligible(frames, floor=MIN_GIANT_COMPONENT_FRAC):
    """({project: DataFrame}, excluded_names) for giant-component descriptors.

    A project qualifies when its median giant_component_frac clears the floor.
    Corpora without the column are all eligible, which is the current two-project
    case. Returns an empty mapping rather than falling back to everything when no
    project qualifies, because silently un-gating would render exactly the figure
    the gate exists to prevent.
    """
    have = [df for df in frames.values() if GIANT_COMPONENT_COLUMN in df.columns]
    if not have:
        return frames, []
    kept, excluded = {}, []
    for project, df in frames.items():
        frac = df.get(GIANT_COMPONENT_COLUMN)
        if frac is None or float(frac.median()) >= floor:
            kept[project] = df
        else:
            excluded.append(project)
    return kept, excluded


def fig_descriptor_trajectories(frames, descriptors, fig_dir,
                                floor=MIN_GIANT_COMPONENT_FRAC,
                                eligible=None, excluded=None, tiers=None):
    """One panel per deterministic descriptor, every project overlaid.

    Gating is per panel, not per figure. D2 and D4 are computed on the whole
    graph and keep every project; only the D1 and D3 panels drop projects whose
    giant component is too small for the descriptor to describe the graph the
    axis reports.
    """
    if not descriptors:
        return []
    if eligible is None:
        eligible, excluded = component_eligible(frames, floor)
    excluded = excluded or []
    n = len(frames)
    thin = n > LEGEND_MAX_PROJECTS
    k = len(descriptors)
    ncols = 2 if k > 1 else 1
    nrows = math.ceil((k + 1) / ncols) if k % ncols == 0 else math.ceil(k / ncols)
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(FULL_W if ncols > 1 else COL_W, nrows * 1.35 + 0.4),
        sharex=True, squeeze=False,
    )
    flat = axes.ravel()
    order = {p: i for i, p in enumerate(frames)}
    tiers = tiers or {}
    split = thin and set(tiers.values()) >= {"core", "extended"}
    TIER_COLOR = {"core": "#0072B2", "extended": "#D55E00"}

    for ax, desc in zip(flat, descriptors):
        gated = is_component_gated(desc)
        shown = eligible if gated else frames
        curves, by_tier = [], {"core": [], "extended": []}
        for project, df in shown.items():
            years = relative_years(df)
            vals = df[desc].astype(float).values
            curves.append((years, vals))
            tier = tiers.get(project)
            if split and tier in by_tier:
                by_tier[tier].append((years, vals))
            ax.plot(
                years, vals,
                color=MUTED if thin else SERIES_PALETTE[order[project] % len(SERIES_PALETTE)],
                linewidth=0.6 if thin else 1.0,
                alpha=0.30 if thin else 1.0,
                label=None if thin else label_of(project),
            )
        if split and all(by_tier.values()):
            # Two populations. Pooling their medians hides that they differ.
            for tier, curves_t in by_tier.items():
                median_band(ax, curves_t, color=TIER_COLOR[tier],
                            label=f"{tier} ($n$={len(curves_t)})")
        else:
            median_band(ax, curves)
        title = desc.replace("_", " ")
        if gated:
            # The real fix for "the axis reports an N the descriptor never saw".
            title += f", {LWCC_SUFFIX}"
            if excluded:
                title += f" ($-${len(excluded)})"
        ax.set_title(title, fontsize=7.5, pad=3)
        if not shown:
            ax.text(0.5, 0.5, "no eligible project", transform=ax.transAxes,
                    ha="center", va="center", fontsize=6.5, color="#666666")
        ax.grid(axis="y")
        ax.tick_params(labelsize=6.5)

    if excluded:
        wrapped_supxlabel(
            fig,
            f"LWCC panels are computed on the largest weakly connected component, "
            f"not on all N nodes. They exclude {len(excluded)} of {len(frames)} "
            f"projects whose median component is below {floor:g} of N, marked "
            f"-{len(excluded)}. D2 and D4 are whole-graph and use every project.",
            FULL_W if ncols > 1 else COL_W,
        )
    blank_unused(flat, k)
    handles, labels = flat[0].get_legend_handles_labels()
    if handles and k < len(flat):
        flat[k].legend(handles, labels, loc="center", handlelength=2.0, fontsize=7.5)
    elif handles:
        fig.legend(handles, labels, loc="lower center", ncol=4,
                   bbox_to_anchor=(0.5, -0.02))
    for ax in flat[max(0, k - ncols):k]:
        ax.set_xlabel("Years since first snapshot", fontsize=7.5)
        ax.tick_params(labelbottom=True)
    fig.tight_layout(pad=0.4)
    return save(fig, "figB_descriptor_trajectories", fig_dir)


def fig_contraction_and_drift(frames, drift, tiers, fig_dir):
    """Two corpus-level distributions that only exist at corpus scale.

    (a) how far each project ends below its own node peak, (b) drift events per
    snapshot. Split by tier where the release defines one, because the two tiers
    are different populations and pooling them hides that.
    """
    rows = []
    for project, df in frames.items():
        years = max((df["date"].max() - df["date"].min()).days, 1) / 365.25
        events = int((drift["project"] == project).sum()) if not drift.empty else 0
        rows.append({
            "project": project,
            "tier": tiers.get(project, "all"),
            "contraction": 100.0 * (1.0 - df["N"].iloc[-1] / df["N"].max()),
            "ends_below_start": df["N"].iloc[-1] < df["N"].iloc[0],
            "drift_per_snapshot": events / len(df),
            "median_N": float(df["N"].median()),
        })
    stats = pd.DataFrame(rows)
    groups = ([("core", "#0072B2"), ("extended", "#D55E00")]
              if set(stats["tier"]) >= {"core", "extended"} else [("all", "#0072B2")])

    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.7))

    ax = axes[0]
    for tier, color in groups:
        vals = stats.loc[stats["tier"] == tier, "contraction"].values
        if not len(vals):
            continue
        x, y = ecdf(vals)
        ax.step(x, y, where="post", color=color,
                label=f"{tier} ($n$={len(vals)})")
    flat = float((stats["contraction"] <= 0).mean())
    ax.axvline(0, color=MUTED, linewidth=0.6, linestyle=":")
    ax.text(0.02, 0.94, f"{flat:.0%} never fall below their peak",
            transform=ax.transAxes, fontsize=6, color="#333333", va="top")
    ax.set_xlabel("Percent below own node peak at last snapshot")
    ax.set_ylabel("ECDF")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y")
    ax.legend(loc="lower right", handlelength=1.6, borderaxespad=0.2)

    ax = axes[1]
    for tier, color in groups:
        vals = stats.loc[stats["tier"] == tier, "drift_per_snapshot"].values
        if not len(vals):
            continue
        x, y = ecdf(vals)
        ax.step(x, y, where="post", color=color,
                label=f"{tier} ($n$={len(vals)})")
    zero = int((stats["drift_per_snapshot"] == 0).sum())
    note = f"{zero} of {len(stats)} projects never drift"
    # Drift is a relative-change threshold, so a larger graph has more chances to
    # cross it. Report that rather than let a tier gap read as a governance effect.
    if len(stats) >= 20:
        rho, pval = spearmanr(stats["median_N"], stats["drift_per_snapshot"])
        if np.isfinite(rho):
            note += (f"\ndrift vs median $N$: Spearman "
                     f"$\\rho$={rho:+.2f}, $p$={pval:.3f}")
    ax.text(0.02, 0.94, note, transform=ax.transAxes, fontsize=6,
            color="#333333", ha="left", va="top", linespacing=1.4)
    ax.set_xlabel("Drift events per snapshot")
    ax.set_ylabel("ECDF")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y")
    ax.legend(loc="lower right", handlelength=1.6, borderaxespad=0.2)

    panel_tag(axes[0], "(a)")
    panel_tag(axes[1], "(b)")
    fig.align_ylabels(axes)
    fig.tight_layout(pad=0.3)
    return save(fig, "fig3_contraction_and_drift", fig_dir), stats


def fig_layer_composition(frames, cols, fig_dir, max_panels=MAX_PANELS):
    """Stacked composition per project, small multiples. Only if the corpus has it."""
    total = len(frames)
    frames, omitted = capped(frames, max_panels)
    n = len(frames)
    nrows, ncols, figsize = grid_layout(n)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    flat = axes.ravel()
    compact = n > 3
    titles = panel_labels(list(frames))
    names = [c.replace(LAYER_PREFIX, "").replace("n_", "") for c in cols]

    for ax, (project, df) in zip(flat, frames.items()):
        block = df[cols].astype(float).values
        totals = block.sum(axis=1, keepdims=True)
        shares = np.divide(block, totals, out=np.zeros_like(block), where=totals > 0)
        ax.stackplot(
            df["date"], shares.T,
            colors=[SERIES_PALETTE[i % len(SERIES_PALETTE)] for i in range(len(cols))],
            labels=names, linewidth=0,
        )
        ax.set_ylim(0, 1)
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_title(titles[project], fontsize=6.2 if compact else 8, pad=2.5)
        ax.tick_params(labelsize=6 if compact else 7)
        year_axis(ax, compact=compact)

    blank_unused(flat, n)
    handles, labels = flat[0].get_legend_handles_labels()
    note = omitted_note(omitted, total)
    if note:
        handles.append(plt.Line2D([], [], color="none"))
        labels.append(note)
    fig.supylabel("Share of nodes", fontsize=8)
    grid_legend(
        fig, flat, n, handles, labels, "Snapshot date", figsize,
        ncol=min(len(cols), 5),
    )
    fig.tight_layout(pad=0.3, h_pad=0.7, w_pad=0.6, rect=[0.022, 0, 1, 1])
    return save(fig, "figC_layer_composition", fig_dir)


def fig_coverage_trajectories(frames, cols, fig_dir):
    """Documentation and test coverage over time. Only if the corpus has it."""
    canonical = [c for c in ("doc_rate", "test_rate") if c in cols]
    fig, axes = plt.subplots(
        len(canonical), 1, figsize=(COL_W, 1.8 * len(canonical) + 0.3),
        sharex=True, squeeze=False,
    )
    flat = axes.ravel()
    thin = len(frames) > LEGEND_MAX_PROJECTS
    titles = {"doc_rate": "Documented share", "test_rate": "Tested share"}

    for ax, key in zip(flat, canonical):
        curves = []
        for i, (project, df) in enumerate(frames.items()):
            years = relative_years(df)
            vals = df[cols[key]].astype(float).values
            curves.append((years, vals))
            ax.plot(
                years, vals,
                color=MUTED if thin else SERIES_PALETTE[i % len(SERIES_PALETTE)],
                linewidth=0.6 if thin else 1.0,
                alpha=0.45 if thin else 1.0,
                label=None if thin else label_of(project),
            )
        median_band(ax, curves)
        ax.set_ylabel(titles[key])
        ax.set_ylim(0, 1)
        ax.grid(axis="y")

    flat[0].legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)
    flat[-1].set_xlabel("Years since first snapshot")
    for i, ax in enumerate(flat):
        panel_tag(ax, f"({chr(97 + i)})")
    fig.align_ylabels(flat)
    fig.tight_layout(pad=0.3)
    return save(fig, "figD_coverage_trajectories", fig_dir)


def fig_degree_distribution(frames, paths, fig_dir, max_panels=MAX_PANELS):
    """First against last snapshot degree distribution, per project, log-log CCDF."""
    usable = {}
    for project, path in paths.items():
        df = pd.read_csv(path)
        if not {"date", "degree"} <= set(df.columns):
            continue
        df["date"] = pd.to_datetime(df["date"])
        usable[project] = df
    if not usable:
        return []

    total = len(usable)
    usable, omitted = capped(usable, max_panels)
    n = len(usable)
    nrows, ncols, figsize = grid_layout(n, panel_h_small=1.3, panel_h_large=0.95)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    flat = axes.ravel()

    for ax, (project, df) in zip(flat, usable.items()):
        for when, color, marker in (
            ("first", METRIC_COLOR["N"], "o"), ("last", METRIC_COLOR["M"], "s")
        ):
            stamp = df["date"].min() if when == "first" else df["date"].max()
            deg = df.loc[df["date"] == stamp, "degree"].astype(float).values
            deg = deg[deg > 0]
            if len(deg) == 0:
                continue
            x, y = ecdf(deg)
            # Complementary CDF on log-log is the standard read for a heavy tail.
            ax.plot(x, 1.0 - y + 1e-9, color=color, marker=marker,
                    markersize=1.8, linewidth=0.8, label=when)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(panel_labels(list(usable))[project], fontsize=6.5, pad=2.5)
        ax.tick_params(labelsize=6)
        ax.grid(which="major", alpha=0.25)

    blank_unused(flat, n)
    handles, labels = flat[0].get_legend_handles_labels()
    note = omitted_note(omitted, total)
    if note:
        handles.append(plt.Line2D([], [], color="none"))
        labels.append(note)
    fig.supylabel(r"$P(\mathrm{degree} \geq x)$", fontsize=8)
    grid_legend(fig, flat, n, handles, labels, "Degree", figsize, ncol=2)
    fig.tight_layout(pad=0.3, h_pad=0.7, w_pad=0.6, rect=[0.028, 0, 1, 1])
    return save(fig, "figE_degree_distribution", fig_dir)


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
    # Second pass, after $ is escaped. In text mode < > | render as inverted
    # punctuation rather than the intended glyph.
    for char, repl in [
        ("≥", r"$\geq$"), ("≤", r"$\leq$"),
        ("<", r"\textless{}"), (">", r"\textgreater{}"), ("|", r"\textbar{}"),
    ]:
        out = out.replace(char, repl)
    return out


def tex_int(value):
    return f"{int(value):,}".replace(",", "{,}")


def write_table(stem, frame, tex_body, tab_dir):
    csv_path = tab_dir / f"{stem}.csv"
    tex_path = tab_dir / f"{stem}.tex"
    frame.to_csv(csv_path, index=False)
    tex_path.write_text(tex_body)
    return [csv_path, tex_path]


def table_dataset_characterization(frames, drift, tab_dir, max_rows):
    rows = []
    for project, df in frames.items():
        span_days = int((df["date"].max() - df["date"].min()).days)
        years = span_days / 365.25
        events = int((drift["project"] == project).sum()) if not drift.empty else 0
        rows.append(
            {
                "project": label_of(project),
                "project_id": project,
                "snapshots": len(df),
                "date_start": df["date"].min().strftime("%Y-%m-%d"),
                "date_end": df["date"].max().strftime("%Y-%m-%d"),
                "span_days": span_days,
                "span_years": round(years, 3),
                "nodes_first": int(df["N"].iloc[0]),
                "nodes_last": int(df["N"].iloc[-1]),
                "nodes_min": int(df["N"].min()),
                "nodes_max": int(df["N"].max()),
                "nodes_peak_date": df["date"].iloc[int(df["N"].idxmax())].strftime("%Y-%m-%d"),
                "edges_first": int(df["M"].iloc[0]),
                "edges_last": int(df["M"].iloc[-1]),
                "edges_min": int(df["M"].min()),
                "edges_max": int(df["M"].max()),
                "node_growth_multiple": round(growth_multiple(df["N"]), 2),
                "edge_growth_multiple": round(growth_multiple(df["M"]), 2),
                "net_contraction_from_peak_pct": round(
                    100.0 * (1.0 - df["N"].iloc[-1] / df["N"].max()), 1
                ),
                "drift_events": events,
                "drift_events_per_year": round(events / years, 2) if years > 0 else None,
                "median_snapshot_gap_days": float(df["date"].diff().dt.days.dropna().median()),
                "max_snapshot_gap_days": float(df["date"].diff().dt.days.dropna().max()),
            }
        )
    frame = pd.DataFrame(rows)
    # Round once, at the end. Summing per-project rounded years and rounding again
    # moves the corpus total.
    cumulative_years = float(frame["span_days"].sum()) / 365.25
    total = {
        "project": "All",
        "snapshots": int(frame["snapshots"].sum()),
        "date_start": frame["date_start"].min(),
        "date_end": frame["date_end"].max(),
        "span_days": int(frame["span_days"].sum()),
        "span_years": round(cumulative_years, 3),
        "drift_events": int(len(drift)),
    }
    frame = pd.concat([frame, pd.DataFrame([total])], ignore_index=True)
    # The All row has no per-project counts, which would otherwise upcast the count
    # columns to float and write "74.0" where the source says 74.
    for col in frame.columns:
        if col.startswith(("nodes_", "edges_")) and not col.endswith("_date"):
            frame[col] = frame[col].astype("Int64")

    shown = rows[:max_rows]
    omitted = len(rows) - len(shown)
    contracting = sum(1 for r in rows if r["net_contraction_from_peak_pct"] > 0)
    note = (
        "Growth is the last snapshot over the first. "
        f"{contracting} of {len(rows)} projects end below their own node peak, so a "
        "growth multiple is not the full range a graph traverses."
    )
    caption = [
        r"  \caption{Longitudinal dbt lineage corpus. One snapshot per 30-day window",
        r"    of commits touching the models path. Drift counts step changes above",
        r"    20\% in a descriptor that is free of D1. Long project ids are elided;",
        r"    the released CSV carries them in full.}",
        r"  \label{tab:dataset}",
    ]

    wide = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table*}[t]",
        r"  \centering",
        r"  \footnotesize",
        *caption,
        r"  \setlength{\tabcolsep}{4pt}",
        r"  \begin{tabular}{lrlrrrrrrr}",
        r"    \toprule",
        r"    & & & \multicolumn{2}{c}{Nodes $N$} & \multicolumn{2}{c}{Edges $M$}"
        r" & & & \\",
        r"    \cmidrule(lr){4-5}\cmidrule(lr){6-7}",
        r"    Project & Snap. & Date span & first$\to$last & min--max"
        r" & first$\to$last & min--max & $N\times$ & $M\times$ & Drift \\",
        r"    \midrule",
    ]
    for r in shown:
        wide.append(
            "    {p} & {s} & {d0} -- {d1} & {n0}$\\to${n1} & {nmin}--{nmax} & "
            "{m0}$\\to${m1} & {mmin}--{mmax} & {ng}$\\times$ & {mg}$\\times$ & "
            "{dr} \\\\".format(
                p=tex_escape(elide(r["project"], 20)), s=r["snapshots"],
                d0=r["date_start"][:7], d1=r["date_end"][:7],
                n0=tex_int(r["nodes_first"]), n1=tex_int(r["nodes_last"]),
                nmin=tex_int(r["nodes_min"]), nmax=tex_int(r["nodes_max"]),
                m0=tex_int(r["edges_first"]), m1=tex_int(r["edges_last"]),
                mmin=tex_int(r["edges_min"]), mmax=tex_int(r["edges_max"]),
                ng=f"{r['node_growth_multiple']:.1f}",
                mg=f"{r['edge_growth_multiple']:.1f}",
                dr=r["drift_events"],
            )
        )
    if omitted:
        wide.append(
            "    \\multicolumn{{10}}{{l}}{{\\textit{{\\ldots{{}} and {n} further "
            "projects, in the released CSV}}}} \\\\".format(n=omitted)
        )
    wide += [
        r"    \midrule",
        "    All & {s} & {d0} -- {d1} & \\multicolumn{{4}}{{c}}"
        "{{{y} cumulative years}} & & & {dr} \\\\".format(
            s=total["snapshots"], d0=total["date_start"][:7],
            d1=total["date_end"][:7], y=f"{cumulative_years:.1f}",
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
    written = write_table("table1_dataset_characterization", frame, "\n".join(wide), tab_dir)

    # Transposed single-column rendering. Only meaningful for a handful of
    # projects, so it is emitted only when it would actually fit a column.
    if len(rows) <= 4:
        metrics = [
            ("Snapshots", lambda r: str(r["snapshots"])),
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
            *caption,
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
            "  Corpus totals, {s} snapshots over {y} cumulative years with {dr} "
            "drift events. {note}".format(
                s=total["snapshots"], y=f"{cumulative_years:.1f}",
                dr=total["drift_events"], note=note,
            ),
            r"  \end{minipage}",
            r"\end{table}",
            "",
        ]
        path = tab_dir / "table1_dataset_characterization_transposed.tex"
        path.write_text("\n".join(tall))
        written.append(path)
    return written


def table_schema(frames, corpus_dir, tab_dir):
    """Schema of whatever the corpus actually contains, not a fixed list."""
    df = next(iter(frames.values()))
    source = f"longitudinal_<project>.csv, {len(frames)} files in {corpus_dir.name}/"
    records = []
    for col in df.columns:
        typ, desc = FIELD_DOCS.get(col, ("", "Undocumented field, present in the corpus."))
        if not typ:
            typ = (
                "integer" if pd.api.types.is_integer_dtype(df[col])
                else "float" if pd.api.types.is_numeric_dtype(df[col])
                else "string"
            )
        records.append(
            {
                "file": source, "field": col, "type": typ,
                "reproducible": "no" if col in EXCLUDED_FIELDS else "yes",
                "description": desc,
            }
        )
    frame = pd.DataFrame(records)

    body = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table*}[t]",
        r"  \centering",
        r"  \footnotesize",
        r"  \caption{Schema of the released corpus. Every field in every released",
        r"    file. Fields marked not reproducible are excluded from every figure",
        r"    and from Table~\ref{tab:summary}.}",
        r"  \label{tab:schema}",
        r"  \begin{tabular}{llcp{0.55\linewidth}}",
        r"    \toprule",
        r"    Field & Type & Repro. & Description \\",
        r"    \midrule",
    ]
    for r in records:
        body.append(
            "    \\texttt{{{f}}} & {t} & {rep} & {d} \\\\".format(
                f=tex_escape(r["field"]), t=tex_escape(r["type"]),
                rep=r["reproducible"], d=tex_escape(r["description"]),
            )
        )
    body += [r"    \bottomrule", r"  \end{tabular}"]
    if any(r["reproducible"] == "no" for r in records):
        reasons = " ".join(
            f"\\texttt{{{tex_escape(k)}}}. {tex_escape(v)}"
            for k, v in EXCLUDED_FIELDS.items() if k in df.columns
        )
        body += [
            r"  \par\vspace{3pt}",
            r"  \begin{minipage}{\linewidth}\footnotesize\raggedright",
            "  " + reasons,
            r"  \end{minipage}",
        ]
    body += [r"\end{table*}", ""]
    return write_table("table2_schema", frame, "\n".join(body), tab_dir)


def table_summary_statistics(frames, drift, descriptors, tab_dir, eligible=None):
    pooled = pd.concat(
        [df.assign(project=p) for p, df in frames.items()], ignore_index=True
    )
    gated_pool = pooled if eligible is None else pooled[pooled["project"].isin(eligible)]
    # The covariate belongs in the summary table, since every LWCC descriptor
    # above has to be read against it.
    covariate = ([GIANT_COMPONENT_COLUMN]
                 if GIANT_COMPONENT_COLUMN in pooled.columns else [])
    fields = ["N", "M"] + covariate + descriptors
    counts = ("N", "M", "D1_n_comm")

    rows = []
    for col in fields:
        # A giant-component descriptor is summarised over eligible projects only,
        # which is why its n differs from the corpus snapshot count.
        source = gated_pool if is_component_gated(col) else pooled
        s = pd.to_numeric(source[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append(
            {
                "field": col, "n": int(len(s)),
                "min": float(s.min()), "q25": float(s.quantile(0.25)),
                "median": float(s.median()), "mean": float(s.mean()),
                "q75": float(s.quantile(0.75)), "max": float(s.max()),
                "sd": float(s.std(ddof=1)),
            }
        )
    stats_frame = pd.DataFrame(rows)

    gaps = pd.concat(
        [df["date"].diff().dt.days.dropna() for df in frames.values()], ignore_index=True
    )
    cumulative_years = sum(
        (df["date"].max() - df["date"].min()).days for df in frames.values()
    ) / 365.25
    corpus = {
        "projects": len(frames),
        "snapshots": int(len(pooled)),
        "cumulative_years": round(cumulative_years, 3),
        "observation_window_start": pooled["date"].min().strftime("%Y-%m-%d"),
        "observation_window_end": pooled["date"].max().strftime("%Y-%m-%d"),
        "drift_events": int(len(drift)),
        "drift_threshold_pct": DRIFT_THRESHOLD_PCT,
        "drift_descriptors": ",".join(sorted(drift["descriptor"].unique()))
        if not drift.empty else "",
        "excluded_fields": ",".join(sorted(EXCLUDED_FIELDS)),
        "median_snapshot_gap_days": float(gaps.median()),
        "max_snapshot_gap_days": float(gaps.max()),
    }
    frame = pd.concat(
        [pd.DataFrame([{"field": k, "median": v} for k, v in corpus.items()]),
         stats_frame],
        ignore_index=True,
    )

    def fmt(v, col, stat):
        if col in counts:
            # Min, median and max of an integer field are integers. Mean and SD
            # are not, and rounding them to whole numbers loses the spread.
            return f"{v:.0f}" if stat in ("min", "median", "max") else f"{v:.1f}"
        return f"{v:.3f}"

    body = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table}[t]",
        r"  \centering",
        r"  \footnotesize",
        r"  \caption{Corpus summary. Distributions pool all"
        f" {corpus['snapshots']} snapshots across {corpus['projects']} projects."
        r" Field names are defined in Table~\ref{tab:schema}.}",
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
    for r in rows:
        col = r["field"]
        body.append(
            "    \\texttt{{{lab}}}{sfx} & {mn} & {md} & {mu} & {mx} & {sd} \\\\".format(
                lab=tex_escape(col),
                sfx="$^{\\dagger}$" if is_component_gated(col) else "",
                mn=fmt(r["min"], col, "min"), md=fmt(r["median"], col, "median"),
                mu=fmt(r["mean"], col, "mean"), mx=fmt(r["max"], col, "max"),
                sd=fmt(r["sd"], col, "sd"),
            )
        )
    body += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{3pt}",
        r"  \begin{minipage}{\linewidth}\footnotesize\raggedright",
        "  $^{\\dagger}$Computed on the largest weakly connected component, not on "
        "all $N$ nodes. Read against \\texttt{giant\\_component\\_frac} above, and "
        "pooled over projects whose median clears "
        f"{MIN_GIANT_COMPONENT_FRAC:g}.",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return write_table("table3_summary_statistics", frame, "\n".join(body), tab_dir)


def table_order_sensitivity(corpus_dir, tab_dir):
    """Node-order sensitivity per descriptor, from the release's own measurement.

    This is the evidence for excluding D1, measured on real snapshots under
    repeated node permutation rather than argued from one graph.
    """
    for candidate in (corpus_dir / "d1_order_sensitivity.json",
                      corpus_dir.parent / "d1_order_sensitivity.json"):
        if candidate.is_file():
            payload = json.loads(candidate.read_text())
            break
    else:
        return []
    ranges = payload.get("range_across_permutations", {})
    if not ranges:
        return []

    rows = []
    for field, stat in ranges.items():
        rows.append({
            "field": field,
            "n_snapshots": stat.get("n"),
            "median_range": stat.get("median"),
            "max_range": stat.get("max"),
            "mean_range": stat.get("mean"),
            "excluded": "yes" if field in EXCLUDED_FIELDS else "no",
        })
    frame = pd.DataFrame(rows)

    def fmt(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "--"
        if v == 0:
            return "0"
        return f"{v:.4f}" if abs(v) >= 1e-3 else f"{v:.1e}"

    body = [
        "% Generated by paper/dolap_dataset/make_figures.py. Do not edit by hand.",
        r"\begin{table}[t]",
        r"  \centering",
        r"  \footnotesize",
        r"  \caption{Descriptor sensitivity to node insertion order, measured on"
        f" {payload.get('n_snapshots_tested', '?')} corpus snapshots at"
        f" {payload.get('n_permutations_each', '?')} permutations each. Range is"
        r" max minus min across permutations of the same graph. D1 is excluded"
        r" from every figure and from Table~\ref{tab:summary}.}",
        r"  \label{tab:ordersens}",
        r"  \setlength{\tabcolsep}{3.5pt}",
        r"  \begin{tabular}{lrrrc}",
        r"    \toprule",
        r"    Field & Median & Mean & Max & Excluded \\",
        r"    \midrule",
    ]
    for r in rows:
        body.append(
            "    \\texttt{{{f}}} & {md} & {mu} & {mx} & {ex} \\\\".format(
                f=tex_escape(r["field"]), md=fmt(r["median_range"]),
                mu=fmt(r["mean_range"]), mx=fmt(r["max_range"]), ex=r["excluded"],
            )
        )
    body += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return write_table("table4_order_sensitivity", frame, "\n".join(body), tab_dir)


# --------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--corpus", type=Path, default=DEFAULT_CORPUS,
        help=f"Directory of longitudinal_<project>.csv files (default {DEFAULT_CORPUS}).",
    )
    p.add_argument(
        "--out", type=Path, default=OUT_DIR,
        help="Output root; figures/ and tables/ are created under it.",
    )
    p.add_argument(
        "--drift-descriptors", nargs="*", default=None,
        help=f"Descriptors monitored for step changes (default {DEFAULT_DRIFT_DESCRIPTORS}).",
    )
    p.add_argument(
        "--ignore-tier", action="store_true",
        help="Ignore corpus_index.csv tiers and gate D1/D3 on "
             "--giant-component-floor instead. Sensitivity analysis only.",
    )
    p.add_argument(
        "--giant-component-floor", type=float, default=MIN_GIANT_COMPONENT_FRAC,
        help=f"Minimum median giant_component_frac for a project to appear in D1 "
             f"and D3 panels (default {MIN_GIANT_COMPONENT_FRAC}). Every run prints "
             f"the observed distribution so this can be retuned against real data.",
    )
    p.add_argument(
        "--max-panels", type=int, default=MAX_PANELS,
        help=f"Projects drawn as small multiples before the grid is capped "
             f"(default {MAX_PANELS}). Corpus-level figures always use all of them.",
    )
    p.add_argument(
        "--max-table-rows", type=int, default=15,
        help="Projects printed in the LaTeX table before the rest are summarised.",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    set_style()
    fig_dir = args.out / "figures"
    tab_dir = args.out / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)

    frames, skipped = discover_projects(args.corpus)
    layers = layer_columns(frames)
    coverage = coverage_columns(frames)
    descriptors = descriptor_fields(frames, also_exclude=coverage.values())
    drift_descs = [
        d for d in (args.drift_descriptors or DEFAULT_DRIFT_DESCRIPTORS)
        if d in descriptors
    ]
    tiers, index_path = load_tiers(args.corpus)
    # Gate on the connectivity cut alone. Tier also encodes snapshot count and
    # peak size, which are sampling criteria rather than validity ones, so tier
    # is used to split the population in the figures, not to gate it.
    eligible, excluded = component_eligible(frames, args.giant_component_floor)
    gate_desc = f"median {GIANT_COMPONENT_COLUMN} >= {args.giant_component_floor:g}"
    drift = compute_drift(frames, drift_descs, eligible)

    print(
        f"Corpus {args.corpus}: {len(frames)} projects, "
        f"{sum(len(f) for f in frames.values())} snapshots."
    )
    print(f"  Descriptors plotted: {', '.join(descriptors) or 'none'}")
    print(f"  Excluded: {', '.join(sorted(EXCLUDED_FIELDS)) or 'none'}")
    print(f"  Drift monitored on {', '.join(drift_descs) or 'nothing'}, "
          f"{len(drift)} events.")
    # Print the distribution so the floor is a tunable choice backed by data
    # rather than a number someone picked once and nobody revisited.
    med = pd.Series({p: float(df[GIANT_COMPONENT_COLUMN].median())
                     for p, df in frames.items()
                     if GIANT_COMPONENT_COLUMN in df.columns})
    if len(med):
        q = med.quantile([0, .1, .25, .5, .75, 1]).round(3).to_dict()
        print(f"  {GIANT_COMPONENT_COLUMN} per-project median, deciles "
              f"min {q[0]}, p10 {q[0.1]}, p25 {q[0.25]}, p50 {q[0.5]}, "
              f"p75 {q[0.75]}, max {q[1]}")
    print(f"  D1/D3 gate: {gate_desc}, excludes {len(excluded)} of "
          f"{len(frames)} projects")
    for project, why in skipped:
        print(f"  SKIPPED project {project}: {why}")

    written, unsupported = [], []
    written += fig_growth_trajectories(frames, drift, fig_dir, args.max_panels)
    written += fig_growth_normalized(frames, fig_dir)
    written += fig_drift_characterization(drift, frames, drift_descs, fig_dir)
    written += fig_snapshot_cadence(frames, fig_dir, args.max_panels)
    written += fig_density_evolution(frames, fig_dir)
    written += fig_descriptor_trajectories(
        frames, descriptors, fig_dir, args.giant_component_floor,
        eligible, excluded, tiers,
    )

    if layers:
        written += fig_layer_composition(frames, layers, fig_dir, args.max_panels)
    else:
        unsupported.append((
            "Layer composition over time (figC)",
            f"No layer columns. Emit either two or more columns prefixed "
            f"'{LAYER_PREFIX}' or the counts {list(LAYER_COUNT_COLUMNS)} in each "
            f"longitudinal_<project>.csv and this figure appears with no code change.",
        ))

    if coverage:
        written += fig_coverage_trajectories(frames, coverage, fig_dir)
    else:
        unsupported.append((
            "Documentation and test coverage (figD)",
            "No coverage columns. Emit one of "
            + " or ".join(str(list(v)) for v in COVERAGE_COLUMNS.values())
            + " per snapshot. The current extractor parses .sql for ref() only and "
            "never reads .yml schema files, so coverage is not measured.",
        ))

    degrees = degree_files(args.corpus, frames)
    if degrees:
        written += fig_degree_distribution(frames, degrees, fig_dir, args.max_panels)
    else:
        unsupported.append((
            "Degree distribution, first against last (figE)",
            f"No per-node degrees. Emit <corpus>/{DEGREE_SUBDIR}/<project>.csv with "
            "columns date,degree, one row per node per snapshot. Snapshots are "
            "currently reduced to scalars at extraction time and the graphs are not "
            "serialised, so no degree sequence survives. figA_density_evolution "
            "substitutes mean degree and density, which are exact arithmetic on N "
            "and M and are not a degree distribution.",
        ))

    contraction_files, contraction_stats = fig_contraction_and_drift(
        frames, drift, tiers, fig_dir
    )
    written += contraction_files
    written += table_dataset_characterization(frames, drift, tab_dir, args.max_table_rows)
    written += table_order_sensitivity(args.corpus, tab_dir)
    written += table_schema(frames, args.corpus, tab_dir)
    # Coverage has its own figure but still belongs in the summary statistics.
    written += table_summary_statistics(
        frames, drift, descriptors + sorted(coverage.values()), tab_dir, eligible
    )

    print(f"\nWrote {len(written)} files under {args.out}:")
    for path in written:
        try:
            print(f"  {path.relative_to(REPO_ROOT)}")
        except ValueError:
            print(f"  {path}")

    if unsupported:
        print("\nNot produced, the corpus cannot support them yet:")
        for name, reason in unsupported:
            print(f"  - {name}\n      {reason}")

    if EXCLUDED_FIELDS:
        print("\nExcluded from every figure and table:")
        for field, reason in EXCLUDED_FIELDS.items():
            print(f"  - {field}\n      {reason}")

    released_drift = args.corpus / "drift_events_refined.csv"
    if released_drift.is_file():
        rel = pd.read_csv(released_drift)
        tainted = int(rel["descriptor"].isin(EXCLUDED_FIELDS).sum())
        if tainted:
            print(
                f"\nWARNING {released_drift.name} is not used. {tainted} of its "
                f"{len(rel)} events are on excluded descriptors. Drift is recomputed "
                f"from the snapshots over {drift_descs}, giving {len(drift)} events."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
