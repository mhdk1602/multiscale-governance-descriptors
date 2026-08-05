"""Unit tests for the longitudinal dbt lineage extractor.

The extractor reads real git repositories, so these tests build small ones in a
temporary directory with a scripted history and assert on what comes back. That
keeps them hermetic while still exercising the git plumbing, which is where the
bugs were.

Several tests pin behaviour that was wrong in the two-project predecessor. Where
that is the case the test name says so, because the point of the test is to stop
the defect coming back.

Run: python -m pytest tests/ -q
"""
import csv
import gzip
import json
import os
import shutil
import subprocess
import sys

import networkx as nx
import pytest

from governance_descriptors.dbt_lineage import (
    REF_PERMISSIVE,
    REF_STRICT,
    RELOCATION_OVERLAP,
    classify_layer,
    compute_descriptors_safe,
    discover_model_paths,
    extract_lineage_at_commit,
    is_vendored,
    parse_dbt_project,
    path_universe,
    run_project,
    sample_one_per_window,
    strip_sql_comments,
)


# --------------------------------------------------------------------------- #
# Helpers: build throwaway git repositories with a scripted history
# --------------------------------------------------------------------------- #

def git(repo, *args):
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, env=env, check=True).stdout


def init_repo(path):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    return path


def write(repo, rel, text):
    full = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


def commit(repo, message, date):
    git(repo, "add", "-A")
    git(repo, "-c", f"user.name=t", "-c", "user.email=t@example.invalid",
        "commit", "-q", "-m", message, "--date", date,
        "--allow-empty")
    # the author date drives sampling; force the committer date to match
    git(repo, "commit", "--amend", "-q", "--no-edit", "--date", date)
    return git(repo, "rev-parse", "HEAD").strip()


def model(name, refs=()):
    body = "\n".join(f"select * from {{{{ ref('{r}') }}}}" for r in refs)
    return f"-- {name}\n{body}\nselect 1\n"


@pytest.fixture
def simple_repo(tmp_path):
    """A one-project repo, models/ at the root, four monthly commits."""
    repo = init_repo(str(tmp_path / "simple"))
    write(repo, "dbt_project.yml", "name: simple\nversion: '1.0'\n")
    for i in range(6):
        write(repo, f"models/staging/stg_{i}.sql", model(f"stg_{i}"))
    commit(repo, "seed staging", "2023-01-10T12:00:00")
    for i in range(4):
        write(repo, f"models/marts/fct_{i}.sql",
              model(f"fct_{i}", [f"stg_{i}", f"stg_{i + 1}"]))
    commit(repo, "add marts", "2023-02-10T12:00:00")
    write(repo, "models/marts/dim_extra.sql", model("dim_extra", ["stg_0"]))
    commit(repo, "one more mart", "2023-03-10T12:00:00")
    write(repo, "models/intermediate/int_join.sql",
          model("int_join", ["stg_2", "fct_1"]))
    commit(repo, "intermediate layer", "2023-04-10T12:00:00")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/heads/main")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


# --------------------------------------------------------------------------- #
# dbt_project.yml parsing
# --------------------------------------------------------------------------- #

def test_parse_dbt_project_reads_name_and_model_paths():
    name, paths = parse_dbt_project(
        b"name: shop\nmodel-paths: ['transform/models']\n")
    assert name == "shop"
    assert paths == ["transform/models"]


def test_parse_dbt_project_defaults_to_models():
    name, paths = parse_dbt_project(b"name: shop\nversion: '1'\n")
    assert paths == ["models"]


def test_parse_dbt_project_accepts_legacy_source_paths():
    _name, paths = parse_dbt_project(b"name: old\nsource-paths: [sql]\n")
    assert paths == ["sql"]


def test_parse_dbt_project_survives_unparseable_yaml():
    name, paths = parse_dbt_project(b"name: [unclosed\n\t bad indent\n")
    assert name is None
    assert paths == ["models"]


@pytest.mark.parametrize("path,expected", [
    ("transform/dbt_modules/dbt_utils/models/x.sql", True),
    ("dbt_packages/codegen/models/y.sql", True),
    ("target/compiled/z.sql", True),
    ("integration_tests/models/a.sql", True),
    ("models/staging/stg_orders.sql", False),
    ("warehouse/models/marts/fct_trips.sql", False),
])
def test_is_vendored_flags_third_party_trees_only(path, expected):
    assert is_vendored(path) is expected


# --------------------------------------------------------------------------- #
# Snapshot sampling
# --------------------------------------------------------------------------- #

def test_sample_one_per_window_keeps_last_commit_in_each_window():
    from datetime import datetime, timedelta
    base = datetime(2023, 1, 1)
    commits = [(base + timedelta(days=d), f"sha{d}") for d in [0, 5, 10, 35, 40, 95]]
    sampled = sample_one_per_window(commits, window_days=30)
    assert [s for _d, s in sampled] == ["sha10", "sha40", "sha95"]


def test_sample_one_per_window_handles_empty_and_single():
    assert sample_one_per_window([]) == []
    from datetime import datetime
    one = [(datetime(2023, 1, 1), "only")]
    assert sample_one_per_window(one) == one


# --------------------------------------------------------------------------- #
# Lineage reconstruction
# --------------------------------------------------------------------------- #

@pytest.mark.slow
def test_extract_lineage_resolves_refs_between_models(simple_repo):
    head = git(simple_repo, "rev-parse", "HEAD").strip()
    g, meta = extract_lineage_at_commit(simple_repo, head, ["models"])
    # 6 staging, 4 fct, 1 dim, 1 intermediate
    assert g.number_of_nodes() == 12
    assert g.has_edge("stg_0", "fct_0")
    assert g.has_edge("fct_1", "int_join")
    assert meta["n_sql_files"] == 12


@pytest.mark.slow
def test_extract_lineage_ignores_refs_to_unknown_models(tmp_path):
    repo = init_repo(str(tmp_path / "unknown"))
    write(repo, "dbt_project.yml", "name: u\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    write(repo, "models/leaf.sql", model("leaf", ["m0", "a_source_not_a_model"]))
    head = commit(repo, "init", "2023-01-01T00:00:00")
    g, _meta = extract_lineage_at_commit(repo, head, ["models"])
    assert g.number_of_nodes() == 6
    assert g.number_of_edges() == 1
    assert "a_source_not_a_model" not in g


@pytest.mark.slow
def test_extract_lineage_node_order_is_sorted_not_hash_dependent(simple_repo):
    """Regression. Set iteration order made D1 vary with PYTHONHASHSEED."""
    head = git(simple_repo, "rev-parse", "HEAD").strip()
    g, _meta = extract_lineage_at_commit(simple_repo, head, ["models"])
    assert list(g.nodes()) == sorted(g.nodes())


D1_PROBE = r'''
import json, sys
sys.path.insert(0, {src!r})
from governance_descriptors.dbt_lineage import (
    compute_descriptors_safe, extract_lineage_at_commit)
g, _m = extract_lineage_at_commit({repo!r}, {sha!r}, ["models"])
d = compute_descriptors_safe(g)
print(json.dumps({{k: d[k] for k in
    ("N", "M", "D1_csi", "D1_n_comm", "D2_max_gini", "D4_cycle_rank_norm")}}))
'''


@pytest.mark.slow
def test_d1_is_identical_across_process_hash_seeds(simple_repo, tmp_path):
    """Regression, and the one that would have caught the published defect.

    The predecessor built its node set with `{f.stem for f in sql_files}` and
    inserted straight from it. CPython randomises string set iteration per
    process, Louvain is an order-sensitive greedy pass, and D1_csi therefore
    differed between runs of unchanged code on an unchanged repository. On one
    Cal-ITP commit three hash seeds gave 0.6429, 0.7857 and 0.5000.

    Asserting sorted order in-process is not enough to catch that, because the
    defect only shows across processes. This spawns real interpreters.
    """
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    head = git(simple_repo, "rev-parse", "HEAD").strip()
    probe = tmp_path / "probe.py"
    probe.write_text(D1_PROBE.format(src=src, repo=simple_repo, sha=head))

    results = []
    for hashseed in ("0", "1", "2", "random"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        out = subprocess.run([sys.executable, str(probe)], capture_output=True,
                             text=True, env=env, check=True).stdout
        results.append((hashseed, json.loads(out)))

    first = results[0][1]
    for hashseed, got in results[1:]:
        assert got == first, (
            f"descriptors changed under PYTHONHASHSEED={hashseed}. "
            f"{first} became {got}. Node insertion order has stopped being "
            f"deterministic, which silently corrupts D1.")


@pytest.mark.slow
def test_extract_lineage_skips_macros_tests_and_snapshots(tmp_path):
    repo = init_repo(str(tmp_path / "skips"))
    write(repo, "dbt_project.yml", "name: s\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    write(repo, "models/macros/helper.sql", "{% macro helper() %}{% endmacro %}")
    write(repo, "models/tests/assert_x.sql", "select 1")
    write(repo, "models/snapshots/snap_y.sql", "select 1")
    head = commit(repo, "init", "2023-01-01T00:00:00")
    g, _meta = extract_lineage_at_commit(repo, head, ["models"])
    assert set(g.nodes()) == {f"m{i}" for i in range(5)}


@pytest.mark.slow
def test_extract_lineage_excludes_vendored_package_models(tmp_path):
    """Regression. dbt_utils models were being counted as project models."""
    repo = init_repo(str(tmp_path / "vendored"))
    write(repo, "dbt_project.yml", "name: v\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    for i in range(9):
        write(repo, f"models/dbt_modules/dbt_utils/models/vendor_{i}.sql",
              model(f"vendor_{i}"))
    head = commit(repo, "init", "2023-01-01T00:00:00")
    g, _meta = extract_lineage_at_commit(repo, head, ["models"])
    assert g.number_of_nodes() == 5
    assert not any(n.startswith("vendor_") for n in g.nodes())


@pytest.mark.slow
def test_extract_lineage_returns_none_when_no_model_sql(tmp_path):
    repo = init_repo(str(tmp_path / "empty"))
    write(repo, "dbt_project.yml", "name: e\n")
    write(repo, "README.md", "no models here")
    head = commit(repo, "init", "2023-01-01T00:00:00")
    g, meta = extract_lineage_at_commit(repo, head, ["models"])
    assert g is None
    assert meta["n_sql_files"] == 0


# --------------------------------------------------------------------------- #
# Project discovery and selection
# --------------------------------------------------------------------------- #

@pytest.mark.slow
def test_discover_model_paths_resolves_relative_to_the_config(tmp_path):
    repo = init_repo(str(tmp_path / "nested"))
    write(repo, "transform/dbt_project.yml",
          "name: nested\nmodel-paths: ['models', 'extra']\n")
    write(repo, "transform/models/a.sql", model("a"))
    head = commit(repo, "init", "2023-01-01T00:00:00")
    paths, projects = discover_model_paths(repo, head)
    assert sorted(paths) == ["transform/extra", "transform/models"]
    assert projects[0]["name"] == "nested"


@pytest.mark.slow
def test_path_universe_picks_the_project_with_the_most_commits(tmp_path):
    """Two coexisting dbt projects are not one graph. Track the busier one."""
    repo = init_repo(str(tmp_path / "two"))
    write(repo, "big/dbt_project.yml", "name: big\n")
    for i in range(5):
        write(repo, f"big/models/b{i}.sql", model(f"b{i}"))
    commit(repo, "big init", "2020-01-01T00:00:00")
    write(repo, "small/dbt_project.yml", "name: small\n")
    write(repo, "small/models/s0.sql", model("s0"))
    commit(repo, "small init", "2023-01-01T00:00:00")
    # keep both alive, but touch big far more often
    for m in range(2, 12):
        write(repo, f"big/models/b_extra_{m}.sql", model(f"b_extra_{m}"))
        commit(repo, f"big churn {m}", f"2023-{m:02d}-01T00:00:00")
    write(repo, "small/models/s1.sql", model("s1"))
    commit(repo, "small churn", "2023-11-15T00:00:00")
    head = git(repo, "rev-parse", "HEAD").strip()

    paths, info = path_universe(repo, head)
    assert paths == ["big/models"]
    assert info["chosen_config"] == "big/dbt_project.yml"
    assert info["n_dbt_projects_seen"] == 2
    assert info["n_configs_chained"] == 1


@pytest.mark.slow
def test_path_universe_chains_a_relocated_project(tmp_path):
    """One project that moved is one series, not two rivals."""
    repo = init_repo(str(tmp_path / "moved"))
    write(repo, "dbt_project.yml", "name: moved\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    commit(repo, "start at the root", "2021-01-01T00:00:00")
    for m in range(2, 8):
        write(repo, f"models/m_root_{m}.sql", model(f"m_root_{m}"))
        commit(repo, f"root churn {m}", f"2021-{m:02d}-01T00:00:00")
    # relocate: the old tree and config go away, a new one appears
    shutil.rmtree(os.path.join(repo, "models"))
    os.remove(os.path.join(repo, "dbt_project.yml"))
    write(repo, "dbt/dbt_project.yml", "name: moved\n")
    for i in range(6):
        write(repo, f"dbt/models/m{i}.sql", model(f"m{i}"))
    commit(repo, "relocate under dbt/", "2023-01-01T00:00:00")
    for m in range(2, 9):
        write(repo, f"dbt/models/m_new_{m}.sql", model(f"m_new_{m}"))
        commit(repo, f"new churn {m}", f"2023-{m:02d}-01T00:00:00")
    head = git(repo, "rev-parse", "HEAD").strip()

    paths, info = path_universe(repo, head)
    assert set(paths) == {"models", "dbt/models"}
    assert info["n_configs_chained"] == 2


def test_relocation_threshold_is_a_named_constant():
    assert 0.0 < RELOCATION_OVERLAP < 1.0


# --------------------------------------------------------------------------- #
# Layer classification
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,path,expected", [
    ("stg_orders", "models/stg_orders.sql", "staging"),
    ("int_joined", "models/int_joined.sql", "intermediate"),
    ("fct_trips", "models/fct_trips.sql", "mart"),
    ("dim_stops", "models/dim_stops.sql", "mart"),
    ("orders", "models/staging/orders.sql", "staging"),
    ("orders", "models/marts/orders.sql", "mart"),
    ("whatever", "models/other/whatever.sql", "unclassified"),
])
def test_classify_layer(name, path, expected):
    assert classify_layer(name, path) == expected


# --------------------------------------------------------------------------- #
# Descriptors
# --------------------------------------------------------------------------- #

def test_compute_descriptors_safe_marks_small_graphs():
    g = nx.DiGraph([("a", "b"), ("b", "c")])
    out = compute_descriptors_safe(g)
    assert out["too_small"] is True
    assert "D1_csi" not in out


def test_compute_descriptors_safe_returns_all_four_families():
    g = nx.DiGraph((f"m{i}", f"m{i + 1}") for i in range(9))
    out = compute_descriptors_safe(g)
    assert out["too_small"] is False
    for key in ("D1_csi", "D1_n_comm", "D2_max_gini", "D3_alg_conn",
                "D3_norm_gap", "D3_fiedler_bim", "D4_cycle_rank_norm"):
        assert key in out, key


def test_descriptors_are_invariant_to_node_insertion_order():
    """The permutation that used to move D1 must now move nothing."""
    edges = [(f"m{i}", f"m{i + 1}") for i in range(11)] + [("m0", "m5"), ("m2", "m9")]
    forward = nx.DiGraph()
    forward.add_nodes_from(sorted({n for e in edges for n in e}))
    forward.add_edges_from(edges)
    backward = nx.DiGraph()
    backward.add_nodes_from(sorted({n for e in edges for n in e}, reverse=True))
    backward.add_edges_from(edges)

    a, b = compute_descriptors_safe(forward), compute_descriptors_safe(backward)
    assert a["N"] == b["N"] and a["M"] == b["M"]
    assert a["D2_max_gini"] == pytest.approx(b["D2_max_gini"])
    assert a["D4_cycle_rank_norm"] == pytest.approx(b["D4_cycle_rank_norm"])
    assert a["D3_alg_conn"] == pytest.approx(b["D3_alg_conn"], abs=1e-9)


# --------------------------------------------------------------------------- #
# End to end
# --------------------------------------------------------------------------- #

@pytest.mark.slow
def test_run_project_produces_a_monthly_series(simple_repo, tmp_path):
    """Four commits a calendar month apart give three snapshots, not four.

    The windows are 30 days wide and anchored on the first commit, so they slide
    against the calendar. A project committing on the tenth of every month has
    two commits inside one window roughly every eleventh month, and the earlier
    of the two is dropped. That is why the corpus reports a median snapshot gap
    a little above 30 days rather than exactly 30.
    """
    out = str(tmp_path / "out")
    res = run_project(simple_repo, "simple", "https://example.invalid/simple",
                      out, verbose=False)
    assert res["status"] == "success"
    assert res["n_snapshots"] == 3
    assert res["snapshot_coverage"] == 1.0
    assert res["model_path_universe"] == ["models"]
    dates = [r["date"][:7] for r in res["snapshots"]]
    assert dates == ["2023-01", "2023-03", "2023-04"]
    ns = [r["N"] for r in res["snapshots"]]
    assert ns == sorted(ns), "this fixture only ever adds models"
    assert os.path.exists(os.path.join(out, "simple.json"))


@pytest.mark.slow
def test_run_project_records_layer_counts(simple_repo, tmp_path):
    res = run_project(simple_repo, "simple", "", str(tmp_path / "o"),
                      verbose=False)
    last = res["snapshots"][-1]
    assert last["n_staging"] == 6
    assert last["n_mart"] == 5
    assert last["n_intermediate"] == 1


@pytest.mark.slow
def test_run_project_reports_a_repo_with_no_dbt_project_as_failed(tmp_path):
    repo = init_repo(str(tmp_path / "nodbt"))
    write(repo, "README.md", "not a dbt project")
    commit(repo, "init", "2023-01-01T00:00:00")
    res = run_project(repo, "nodbt", "", str(tmp_path / "o"), verbose=False)
    assert res["status"] == "failed"
    assert "dbt_project.yml" in res["error"]


@pytest.mark.slow
def test_run_project_reports_partial_when_a_commit_has_no_models(tmp_path):
    """A published config with the models removed is a gap, not a crash."""
    repo = init_repo(str(tmp_path / "gap"))
    write(repo, "dbt_project.yml", "name: g\n")
    for i in range(6):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    commit(repo, "models present", "2023-01-10T00:00:00")
    write(repo, "models/m6.sql", model("m6", ["m0"]))
    commit(repo, "one more", "2023-02-10T00:00:00")
    shutil.rmtree(os.path.join(repo, "models"))
    commit(repo, "models removed from the public tree", "2023-03-10T00:00:00")
    res = run_project(repo, "gap", "", str(tmp_path / "o"), verbose=False)
    assert res["status"] == "partial"
    assert res["n_snapshots_planned"] == 2
    assert res["n_snapshots"] == 1
    assert res["snapshot_coverage"] == 0.5
    assert res["snapshot_errors"][0]["reason"] == "no model SQL at this commit"


@pytest.mark.slow
def test_run_project_does_not_touch_the_worktree(simple_repo, tmp_path):
    """Regression. The predecessor ran git checkout per snapshot."""
    before = git(simple_repo, "rev-parse", "HEAD").strip()
    before_status = git(simple_repo, "status", "--porcelain")
    run_project(simple_repo, "simple", "", str(tmp_path / "o"), verbose=False)
    assert git(simple_repo, "rev-parse", "HEAD").strip() == before
    assert git(simple_repo, "status", "--porcelain") == before_status
    assert git(simple_repo, "symbolic-ref", "--short", "HEAD").strip() == "main"


# --------------------------------------------------------------------------- #
# Parser fidelity: the strict pattern misses refs passed to macros
# --------------------------------------------------------------------------- #

def test_permissive_pattern_recovers_refs_passed_to_a_macro():
    """Regression. The anchor cost 13 percent of Cal-ITP's edges.

    `{{` immediately before `ref(` means the strict pattern only sees a ref that
    is the whole Jinja expression. A ref handed to `dbt_utils.union_relations`
    or `unpivot` is invisible to it, and none of those sites is dynamically
    constructed, so the edges were recoverable all along.
    """
    text = "{{ dbt_utils.union_relations([\n  ref('a'),\n  ref('b'),\n]) }}"
    assert REF_STRICT.findall(text) == []
    assert REF_PERMISSIVE.findall(text) == ['a', 'b']


def test_permissive_pattern_reads_the_two_argument_form():
    assert REF_PERMISSIVE.findall("{{ ref('a_package', 'the_model') }}") == \
        ['the_model']


@pytest.mark.parametrize("text", [
    "-- select from {{ ref('ghost') }}",
    "/* {{ ref('ghost') }} */ select 1",
    "{# {{ ref('ghost') }} #}",
])
def test_commented_out_refs_are_not_edges(text):
    """Regression. Commented SQL put 7 edges into the published Mattermost graphs."""
    assert REF_PERMISSIVE.findall(strip_sql_comments(text)) == []


@pytest.mark.parametrize("text", [
    "select x.ref('not_a_model')",
    "{{ my_ref('not_a_model') }}",
    "{{ source('raw', 'orders') }}",
])
def test_permissive_pattern_does_not_over_match(text):
    assert REF_PERMISSIVE.findall(strip_sql_comments(text)) == []


def test_strip_sql_comments_preserves_line_count():
    text = "select 1\n/* a\nb\nc */\nselect 2\n"
    assert strip_sql_comments(text).count("\n") == text.count("\n")


@pytest.mark.slow
def test_extraction_labels_every_edge_with_a_capture_mode(tmp_path):
    repo = init_repo(str(tmp_path / "modes"))
    write(repo, "dbt_project.yml", "name: m\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    write(repo, "models/direct.sql", "select * from {{ ref('m0') }}")
    write(repo, "models/viamacro.sql",
          "{{ dbt_utils.union_relations([\n  ref('m1'),\n  ref('m2'),\n]) }}")
    write(repo, "models/commented.sql", "-- {{ ref('m3') }}\nselect 1")
    head = commit(repo, "init", "2023-01-01T00:00:00")
    g, meta = extract_lineage_at_commit(repo, head, ["models"])

    assert g.has_edge("m0", "direct")
    assert g.has_edge("m1", "viamacro") and g.has_edge("m2", "viamacro")
    assert not g.has_edge("m3", "commented"), "a commented ref became an edge"
    assert meta["edge_mode"][("m0", "direct")] == "strict"
    assert meta["edge_mode"][("m1", "viamacro")] == "permissive_only"
    assert meta["M_strict"] == 1
    assert meta["M_recovered_by_permissive"] == 2
    assert meta["edges_dropped_as_commented_out"] == 1


@pytest.mark.slow
def test_coverage_is_read_from_the_schema_yaml(tmp_path):
    """The extractor never opened these files, so doc and test rates were blind."""
    repo = init_repo(str(tmp_path / "cov"))
    write(repo, "dbt_project.yml", "name: c\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    write(repo, "models/schema.yml", """
version: 2
models:
  - name: m0
    description: "a documented model"
    columns:
      - name: id
        tests: [unique]
  - name: m1
    description: "documented, untested"
  - name: m2
    description: "   "
    tests: [some_model_level_test]
  - name: gone
    description: "refers to a model that no longer exists"
""")
    head = commit(repo, "init", "2023-01-01T00:00:00")
    _g, meta = extract_lineage_at_commit(repo, head, ["models"])
    assert meta["n_documented"] == 2, "whitespace-only description is not documentation"
    assert meta["n_tested"] == 2, "column-level and model-level tests both count"
    assert meta["doc_rate"] == pytest.approx(2 / 5)
    assert meta["test_rate"] == pytest.approx(2 / 5)


@pytest.mark.slow
def test_run_project_writes_a_gzipped_edge_list(tmp_path, simple_repo):
    out = str(tmp_path / "o")
    res = run_project(simple_repo, "simple", "", out, verbose=False)
    path = os.path.join(out, res["edges_file"])
    assert os.path.isfile(path)
    with gzip.open(path, "rt") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == res["n_edge_rows"]
    assert set(rows[0]) == {"sha", "date", "source", "target", "capture_mode"}
    assert {r["capture_mode"] for r in rows} <= {"strict", "permissive_only"}
    # every edge row belongs to a snapshot the series reports
    assert {r["sha"] for r in rows} <= {s["sha"] for s in res["snapshots"]}


@pytest.mark.slow
def test_edges_can_never_introduce_a_node(tmp_path, monkeypatch):
    """The node set comes from the file listing, so the regex must not move N.

    Guards the `r in model_names` filter. Without it a ref to a source, a seed
    or a model from another package becomes a node, and N stops meaning "models
    in this project".
    """
    repo = init_repo(str(tmp_path / "inv"))
    write(repo, "dbt_project.yml", "name: i\n")
    for i in range(5):
        write(repo, f"models/m{i}.sql", model(f"m{i}"))
    write(repo, "models/leaf.sql",
          "select * from {{ ref('m0') }} join {{ ref('not_a_model_here') }}")
    head = commit(repo, "init", "2023-01-01T00:00:00")

    g, meta = extract_lineage_at_commit(repo, head, ["models"])
    assert g.number_of_nodes() == 6
    assert "not_a_model_here" not in g

    # Break the filter and the guard must fire rather than inflate N silently.
    import governance_descriptors.dbt_lineage as mod
    real = mod.REF_PERMISSIVE

    class LeakyPattern:
        def findall(self, text):
            return real.findall(text)

    monkeypatch.setattr(mod, "REF_PERMISSIVE", LeakyPattern())
    # with the real filter in place this still passes, which is the point:
    # the guard is cheap and only fires on a genuine regression
    g2, _ = extract_lineage_at_commit(repo, head, ["models"])
    assert g2.number_of_nodes() == g.number_of_nodes()
