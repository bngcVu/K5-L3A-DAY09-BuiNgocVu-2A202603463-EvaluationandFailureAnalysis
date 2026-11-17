"""M5-M7 self-check (Advanced/Expert). Run: python -m pytest -q -m student -o addopts= -k advanced
Public vectors only; the instructor grades with hidden ones."""
import copy
import math

import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def stats():
    from lab9 import stats

    return stats


@pytest.mark.parametrize("n,c,k,want", [(5, 5, 5, 1.0), (5, 0, 1, 0.0), (5, 2, 1, 0.4), (10, 3, 3, 1 - 35 / 120)])
def test_pass_at_k(stats, n, c, k, want):
    assert math.isclose(stats.pass_at_k(n, c, k), want, abs_tol=1e-9)


@pytest.mark.parametrize("n,c,k,want", [(5, 5, 5, 1.0), (5, 4, 5, 0.0), (5, 4, 3, 0.4), (10, 8, 2, 28 / 45)])
def test_pass_hat_k(stats, n, c, k, want):
    assert math.isclose(stats.pass_hat_k(n, c, k), want, abs_tol=1e-9)


def test_pass_k_rejects_bad_args(stats):
    for args in [(5, 6, 1), (5, 2, 0), (3, 1, 4)]:
        with pytest.raises(ValueError):
            stats.pass_at_k(*args)


def _report(rows, metrics, items=4, seeds=(1, 2)):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": []}


ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8}}]}


def test_integrity_flags_nan_and_dropped_rows():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    assert gate.integrity_check(base, base, SPEC) == []
    nan = _report(copy.deepcopy(ROWS), {"pass_rate": float("nan")})
    assert gate.integrity_check(nan, base, SPEC)
    dropped = _report(copy.deepcopy(ROWS[:-1]), {"pass_rate": 1.0})
    assert gate.integrity_check(dropped, base, SPEC)


def test_integrity_flags_loosened_spec():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    loose = copy.deepcopy(SPEC)
    loose["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(base, base, loose, SPEC)
    assert gate.integrity_check(base, base, SPEC, SPEC) == []


def test_slice_check_blocks_a_slice_below_floor():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if "denial" in r["slices"] and r["seed"] == 1:
            r["pass_rate"] = False
    spec = dict(SPEC, slices=[{"name": "denial", "metric": "pass_rate", "min": 0.9, "blocking": True}])
    blocked, _ = gate.slice_check(_report(rows, {"pass_rate": 0.75}), base, spec)
    assert blocked == ["slice:denial/pass_rate"]


def _denial_spec(**kw):
    return dict(SPEC, slices=[{"name": "denial", "metric": "pass_rate", "blocking": True, **kw}])


def test_slice_check_blocks_a_significant_drop_above_the_floor():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    for r in rows:                          # both denial items lose one of two seeds: slice = 0.5
        if "denial" in r["slices"] and r["seed"] == 1:
            r["pass_rate"] = False
    blocked, _ = gate.slice_check(_report(rows, {"pass_rate": 0.75}), base,
                                  _denial_spec(min=0.4, no_significant_drop=True))
    assert blocked == ["slice:denial/pass_rate"]


def test_slice_check_non_blocking_slice_only_warns():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if "denial" in r["slices"]:
            r["pass_rate"] = False
    blocked, lines = gate.slice_check(_report(rows, {"pass_rate": 0.5}), base,
                                      _denial_spec(min=0.9, blocking=False))
    assert blocked == [] and any("denial" in ln for ln in lines)


def test_slice_check_clean_pr_passes():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    blocked, lines = gate.slice_check(base, base, _denial_spec(min=0.9, no_significant_drop=True))
    assert blocked == [] and len(lines) == 1


@pytest.mark.parametrize("args", [(5, 6, 1), (5, 2, 0), (3, 1, 4), (5, -1, 1), (0, 0, 1), (5, 2, -1), (5.0, 2, 1), (5, 2, True)])
def test_pass_k_both_reject_bad_args(stats, args):
    for fn in (stats.pass_at_k, stats.pass_hat_k):
        with pytest.raises(ValueError):
            fn(*args)


@pytest.mark.parametrize("n,c", [(5, 0), (5, 1), (5, 3), (5, 5), (10, 7)])
def test_pass_k_ordering(stats, n, c):
    # pass^k <= pass@1 <= pass@k, and k = 1 collapses both to c/n
    for k in range(1, n + 1):
        assert stats.pass_hat_k(n, c, k) <= c / n + 1e-12 <= stats.pass_at_k(n, c, k) + 2e-12
    assert math.isclose(stats.pass_at_k(n, c, 1), c / n) and math.isclose(stats.pass_hat_k(n, c, 1), c / n)


def test_pass_at_k_when_fewer_failures_than_k_is_one(stats):
    assert stats.pass_at_k(5, 3, 3) == 1.0      # only 2 failing runs: any 3 draws include a pass


# --- M7 integrity: hidden-trap style vectors (each must yield >= 1 problem; clean must yield []).
def _base():
    return _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})


def test_integrity_clean_report_against_itself_is_clean():
    from lab9 import gate

    assert gate.integrity_check(_base(), _base(), SPEC) == []


def test_integrity_flags_inf_metric():
    from lab9 import gate

    assert gate.integrity_check(_report(copy.deepcopy(ROWS), {"pass_rate": float("inf")}), _base(), SPEC)


def test_integrity_flags_duplicated_rows_with_same_count():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[-1] = copy.deepcopy(rows[0])        # a failing row replaced by a copy of a passing one
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), _base(), SPEC)


def test_integrity_flags_evaluator_failures_on_a_green_run():
    from lab9 import gate

    rep = _base()
    rep["evaluator_failures"] = ["E-001@1:ApprovalBypass:KeyError"]
    assert gate.integrity_check(rep, _base(), SPEC)


def test_integrity_flags_none_row_value():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[3]["pass_rate"] = None
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), _base(), SPEC)


def test_integrity_flags_cherry_picked_seed_with_consistent_manifest():
    from lab9 import gate

    rows = [r for r in copy.deepcopy(ROWS) if r["seed"] == 1]
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}, seeds=(1,)), _base(), SPEC)


def test_integrity_flags_hand_edited_metric():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False             # rows say 7/8, the metric says 1.0
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), _base(), SPEC)


def test_integrity_flags_relabelled_slice():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    for r in rows:
        r["slices"] = []                     # move denial items out of their slice
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), _base(), SPEC)


SLICED = dict(SPEC, seeds=[1, 2], metrics=[
    {"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.8, "no_significant_drop": True}},
    {"id": "approval_bypass", "kind": "safety", "blocking": True, "threshold": {"max": 0}},
], slices=[{"name": "denial", "metric": "pass_rate", "min": 0.9, "no_significant_drop": True, "blocking": True}])


@pytest.mark.parametrize("loosen", [
    lambda s: s["metrics"][0].update(blocking=False),
    lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
    lambda s: s["metrics"][1]["threshold"].update(max=1),
    lambda s: s["metrics"].pop(1),
    lambda s: s.update(slices=[]),
    lambda s: s["slices"][0].update(min=0.5),
    lambda s: s["slices"][0].pop("no_significant_drop"),
    lambda s: s["slices"][0].update(blocking=False),
    lambda s: s.update(seeds=[1]),
])
def test_integrity_ratchet_flags_every_loosening(loosen):
    from lab9 import gate

    spec = copy.deepcopy(SLICED)
    loosen(spec)
    assert gate.integrity_check(_base(), _base(), spec, SLICED)


def test_integrity_ratchet_allows_stricter_spec_and_new_eval_set_version():
    from lab9 import gate

    strict = copy.deepcopy(SLICED)
    strict["metrics"][0]["threshold"]["min"] = 0.9
    assert gate.integrity_check(_base(), _base(), strict, SLICED) == []
    new_version = copy.deepcopy(SLICED)
    new_version["eval_set_version"] = "v3"
    new_version["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(_base(), _base(), new_version, SLICED) == []
