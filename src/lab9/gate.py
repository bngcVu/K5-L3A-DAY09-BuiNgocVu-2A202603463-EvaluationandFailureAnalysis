"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    rows = pr.get("rows") or []
    man = pr.get("manifest") or {}
    kinds = {m["id"]: m.get("kind") for m in spec.get("metrics") or []}

    # 1. metric values must be finite numbers (NaN < min is False: a naive gate lets it through)
    for mid, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {mid} is {v}")

    # 2. graders must not have crashed, on red AND on green runs
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): first {pr['evaluator_failures'][0]!r}")

    # 3. row count and uniqueness: items x seeds rows, each (item, seed) exactly once
    seeds = list(man.get("seeds") or [])
    want = (man.get("items") or 0) * len(seeds)
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {man.get('items')} items x {len(seeds)} seeds = {want}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dup = sorted({k for k in keys if keys.count(k) > 1}, key=str)
    if dup:
        problems.append(f"duplicated (item, seed) rows: {dup[:3]}")
    stray = sorted({r.get("seed") for r in rows} - set(seeds), key=str)
    if stray:
        problems.append(f"rows use seeds {stray} that are not in the manifest")

    # 4. same (item, seed) grid and seeds as the baseline / the spec (no cherry-picking)
    base_rows = base.get("rows") or []
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if set(keys) != base_keys:
        miss, extra = base_keys - set(keys), set(keys) - base_keys
        problems.append(f"(item, seed) set differs from baseline: {len(miss)} missing, {len(extra)} extra")
    if sorted(seeds) != sorted((base.get("manifest") or {}).get("seeds") or []):
        problems.append(f"seeds {seeds} differ from baseline seeds {(base.get('manifest') or {}).get('seeds')}")
    if spec.get("seeds") is not None and sorted(seeds) != sorted(spec["seeds"]):
        problems.append(f"seeds {seeds} differ from the spec seeds {spec['seeds']}")

    # 5. every graded metric present on every row (a crashed grader scores None and drops out)
    graded = [m for m in kinds if any(m in r for r in rows + base_rows)]
    for m in graded:
        bad = [f"{r.get('item_id')}@{r.get('seed')}" for r in rows if r.get(m) is None]
        if bad:
            problems.append(f"{len(bad)} row(s) have no value for {m}: {bad[:3]}")

    # 6. reported metrics must be what the rows say (hand-edited or stale aggregates)
    problems += _recompute_mismatch(pr, graded, kinds)

    # 7. slice tags per item must match the baseline's (relabelling hides a slice regression)
    def tags(rs: list[dict]) -> dict:
        out: dict[str, set] = {}
        for r in rs:
            out.setdefault(r.get("item_id"), set()).update(r.get("slices") or [])
        return out
    pt, bt = tags(rows), tags(base_rows)
    relabelled = sorted(i for i in set(pt) & set(bt) if pt[i] != bt[i])
    if relabelled:
        problems.append(f"slice tags differ from baseline on {relabelled[:3]}")

    # 8. ratchet: on the same eval-set version thresholds may only get stricter
    if base_spec is not None:
        problems += _ratchet(spec, base_spec)
    return problems


def _recompute_mismatch(pr: dict, graded: list[str], kinds: dict) -> list[str]:
    """Recompute row-level aggregates (and pass_hat_k / pass_at_k / pass_5 from pass_rate rows)."""
    rows, reported = pr.get("rows") or [], pr.get("metrics") or {}
    out: list[str] = []

    def differs(name: str, val: float | None) -> None:
        got = reported.get(name)
        if val is None or not isinstance(got, (int, float)) or isinstance(got, bool) or not math.isfinite(got):
            return                                           # missing / non-finite handled elsewhere
        if abs(float(got) - val) > 1e-3:
            out.append(f"metric {name}={got} but rows give {round(val, 4)}")

    for m in graded:
        vals = [r[m] for r in rows if r.get(m) is not None]
        if m in reported and vals:
            differs(m, float(sum(vals)) if kinds.get(m) == "safety" else sum(vals) / len(vals))
    by_item: dict = {}
    for r in rows:
        if r.get("pass_rate") is not None:
            by_item.setdefault(r.get("item_id"), []).append(bool(r["pass_rate"]))
    if by_item:
        differs("pass_5", sum(all(v) for v in by_item.values()) / len(by_item))
        n_min = min(len(v) for v in by_item.values())
        for name in reported:
            for prefix, fn in (("pass_hat_", stats.pass_hat_k), ("pass_at_", stats.pass_at_k)):
                if name.startswith(prefix) and name[len(prefix):].isdigit():
                    k = int(name[len(prefix):])
                    if 1 <= k <= n_min:
                        differs(name, sum(fn(len(v), sum(v), k) for v in by_item.values()) / len(by_item))
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Same eval-set version => every threshold, blocking flag, slice and seed may only get stricter."""
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []                                            # new eval set: thresholds start over
    out: list[str] = []

    def compare(where: str, new: dict | None, old: dict, th_new: dict, th_old: dict) -> None:
        if new is None:
            out.append(f"ratchet: {where} removed")
            return
        if old.get("blocking") and not new.get("blocking"):
            out.append(f"ratchet: {where} no longer blocking")
        for key, looser in (("max", lambda a, b: a > b), ("max_increase", lambda a, b: a > b),
                            ("min", lambda a, b: a < b)):
            if key in th_old and (key not in th_new or looser(th_new[key], th_old[key])):
                out.append(f"ratchet: {where} {key} {th_old[key]} -> {th_new.get(key, 'removed')}")
        if th_old.get("no_significant_drop") and not th_new.get("no_significant_drop"):
            out.append(f"ratchet: {where} dropped no_significant_drop")

    new_m = {m["id"]: m for m in spec.get("metrics") or []}
    for m in base_spec.get("metrics") or []:
        n = new_m.get(m["id"])
        compare(f"metric {m['id']}", n, m, (n or {}).get("threshold") or {}, m.get("threshold") or {})
    new_s = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        n = new_s.get((s["name"], s["metric"]))
        compare(f"slice {s['name']}/{s['metric']}", n, s, n or {}, s)
    if base_spec.get("seeds") and set(base_spec["seeds"]) - set(spec.get("seeds") or []):
        out.append(f"ratchet: seeds {base_spec['seeds']} -> {spec.get('seeds')}")
    bs_old, bs_new = base_spec.get("bootstrap") or {}, spec.get("bootstrap") or {}
    if bs_new.get("confidence", 0.95) < bs_old.get("confidence", 0.95):
        out.append(f"ratchet: bootstrap confidence {bs_old.get('confidence')} -> {bs_new.get('confidence')}")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", f"{len(a)} item(s)"
        if val is None:
            verdict = "missing"            # an empty slice cannot vouch for anything: never a silent pass
        elif "min" in sl and val < sl["min"]:
            verdict = "fail"
        if sl.get("no_significant_drop") and val is not None:
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000),
                                                   rng=bs.get("rng", 2027),
                                                   confidence=bs.get("confidence", 0.95))
                note = f"{len(a)} item(s) Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {sid:<34} {val!s:<8} {json.dumps(th):<40} {note:<40} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
