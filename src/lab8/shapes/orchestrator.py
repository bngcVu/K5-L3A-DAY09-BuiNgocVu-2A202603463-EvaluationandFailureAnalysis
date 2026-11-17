"""Shape C — orchestrator plus a read-only investigator.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

from contextlib import closing

from lab8 import durability
from lab8.db import connect
from lab8.handoff import HandoffError, make_handoff
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    budget = Budget()

    with closing(connect(store_path)) as conn:
        def finish_run(status: str, proposal_amount: int = 0, reason: str | None = None) -> RunResult:
            trace.add("decision", {"status": status, "reason": reason})
            if status != "failed":
                complete(budget, seed=seed, purpose="draft", prompt=status)
            return finish(
                conn,
                shape=SHAPE,
                claim_id=claim_id,
                seed=seed,
                status=status,
                proposal_amount=proposal_amount,
                budget=budget,
                trace=trace,
                error_reason=reason,
            )

        budget.add_tool(tool_cost())
        claim = get_claim_view(conn, claim_id)
        if not claim["found"]:
            return finish_run("failed", reason="unknown_claim")
        if not claim["order_id"]:
            return finish_run("needs_info", reason="missing_order_id")

        try:
            handoff = make_handoff(
                request_id=trace.run_id,
                claim_id=claim_id,
                task="lookup_owned_order",
                facts={},
                allowed_tools=["lookup_order"],
            )
            trace.add("handoff", handoff)
            investigated = run_readonly_investigators(conn, budget, handoff, claim["principal_id"])
        except (HandoffError, ToolRejected):
            return finish_run("failed", reason="investigation_rejected")

        order_view = investigated["tools"]["lookup_order"]
        trace.add("investigator", {"tool": "lookup_order", "visible": order_view["visible"]})
        if not order_view["visible"]:
            return finish_run("escalated", reason=order_view["reason"])

        budget.add_tool(tool_cost())
        quote = compute_compensation(conn, order_view["order"])
        proposal = int(quote["amount_vnd"])
        trace.add("quote", {"amount_vnd": proposal, "reason": quote["reason"]})
        if proposal <= 0:
            return finish_run("denied", reason=quote["reason"])

        # The host applies the per-order cap and approval to the full quote.
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"]})
        if outcome["ok"]:
            return finish_run("resolved", proposal)
        status = "failed" if outcome["conflict"] else "denied"
        return finish_run(status, proposal, outcome["reason"])
