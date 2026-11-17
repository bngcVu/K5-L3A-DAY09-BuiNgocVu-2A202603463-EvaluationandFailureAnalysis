"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _finish(conn, claim_id, seed, status, proposal, budget, trace, reason=None) -> RunResult:
    return finish(
        conn,
        shape=SHAPE,
        claim_id=claim_id,
        seed=seed,
        status=status,
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=reason,
    )


def _make_decide(claim_id: str, *, seed: int, budget: Budget, trace: Trace, memory: dict[str, Any]):
    """The agent policy. Only read tools; facts come from tool results, never from ticket text.

    run_react only hands back the last tool result, so the agent keeps its own scratchpad
    (`memory`). Each step is one counted model call.
    """
    step = {"n": 0}

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        last_tool = seen.get("last_tool")
        if last_tool:
            memory[last_tool] = seen.get("last_result") or {}
        step["n"] += 1
        complete(budget, seed=seed, purpose="react", prompt=f"{claim_id}|step={step['n']}|last={last_tool}")
        action = _next_action(claim_id, memory)
        payload = {"step": step["n"]}
        if "tool" in action:
            payload["tool"] = action["tool"]
        else:
            payload["final"] = action["final"]
        trace.add("react_step", payload)
        return action

    return decide


def _next_action(claim_id: str, memory: dict[str, Any]) -> dict[str, Any]:
    claim = memory.get("get_claim_view")
    if claim is None:
        return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}
    if not claim.get("found"):
        return {"final": {"status": "failed", "error_reason": "unknown_claim"}}
    if not claim.get("order_id"):
        return {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}

    principal = claim["principal_id"]
    order_view = memory.get("lookup_order")
    if order_view is None:
        return {"tool": "lookup_order", "args": {"order_id": claim["order_id"], "principal_id": principal}}
    if not order_view.get("visible"):
        return {"final": {"status": "escalated", "error_reason": order_view.get("reason")}}

    if "lookup_refund_history" not in memory:
        return {"tool": "lookup_refund_history", "args": {"order_id": claim["order_id"], "principal_id": principal}}
    if "compute_compensation" not in memory:
        # The order comes from the DB row, not from numbers written in the ticket.
        return {"tool": "compute_compensation", "args": {"order": order_view["order"]}}
    return {"final": {"status": "quote_ready"}}


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    memory: dict[str, Any] = {}

    try:
        loop = run_react(
            conn,
            budget,
            observation={"claim": {"claim_id": claim_id}},
            decide=_make_decide(claim_id, seed=seed, budget=budget, trace=trace, memory=memory),
            max_steps=MAX_STEPS,
        )
    except (ToolRejected, KeyError, TypeError, ValueError) as exc:
        trace.add("error", {"reason": "tool_error", "type": type(exc).__name__})
        return _finish(conn, claim_id, seed, "failed", 0, budget, trace, "tool_error")

    final = loop["final"]
    status = final.get("status")
    if loop["stopped"] == "step_cap":
        trace.add("decision", {"status": "failed", "reason": "step_cap"})
        return _finish(conn, claim_id, seed, "failed", 0, budget, trace, "step_cap")

    if status in ("failed", "needs_info", "escalated"):
        reason = final.get("error_reason")
        if status != "failed":
            complete(budget, seed=seed, purpose="draft", prompt=status)
        trace.add("decision", {"status": status, "reason": reason})
        return _finish(conn, claim_id, seed, status, 0, budget, trace, reason)

    # After the loop, code (not the model) owns the money: recompute the quote from the
    # allowlisted order row the read tool returned.
    order = memory["lookup_order"]["order"]
    trace.add("order", order)
    history = memory.get("lookup_refund_history") or {}
    trace.add("refund_history", {"refunded_vnd": history.get("refunded_vnd", 0), "refund_count": history.get("refund_count", 0)})
    quote = compute_compensation(conn, order)
    trace.add("quote", quote)
    proposal = int(quote["amount_vnd"])

    if proposal <= 0:
        complete(budget, seed=seed, purpose="draft", prompt="denied")
        trace.add("decision", {"status": "denied", "reason": quote["reason"]})
        return _finish(conn, claim_id, seed, "denied", 0, budget, trace, quote["reason"])

    # Full quote to the host: it checks approval, per-order cap, idempotency.
    # InjectedCrash must propagate.
    try:
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except durability.InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return _finish(conn, claim_id, seed, status, proposal, budget, trace, outcome["reason"])
    return _finish(conn, claim_id, seed, "resolved", proposal, budget, trace, None)
