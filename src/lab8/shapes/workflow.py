"""Shape A — deterministic workflow. Student work.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Suggested steps. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> status `needs_info`. Do not write the ledger.
3. `lookup_order`. If not visible -> `escalated`. Do not copy phone, address, item, internal note.
4. Quote from the order row. Ignore delay numbers written in the ticket.
5. Quote amount 0 -> `denied`. Do not call issue_refund.
6. Quote amount > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`.
   Pass the FULL quote. The host checks the claim's own approval and subtracts
   what earlier claims already got for the same order (T13, T14). Do not
   subtract it yourself or the host subtracts twice.
   Auth failure or order already refunded -> `denied` (the host writes `policy_denied`).
   `proposal_amount` stays the full quote. Amount conflict -> `failed`.
7. Success -> `resolved`. One ledger row, one `refund_committed` audit.
8. Use MockLLM only to draft the reply text, if you want a model call at all.

The model must not choose the refund amount and must not commit the refund.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"


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


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    # Step 1: read the claim through the allowlisted view (never SELECT *).
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        trace.add("error", {"reason": "unknown_claim"})
        return _finish(conn, claim_id, seed, "failed", 0, budget, trace, "unknown_claim")

    # Step 2: no order_id on the claim row -> needs_info. The ticket text is never parsed.
    order_id = claim["order_id"]
    if not order_id:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
        return _finish(conn, claim_id, seed, "needs_info", 0, budget, trace, "missing_order_id")

    # Step 3: order must exist and belong to the claim's principal.
    budget.add_tool(tool_cost())
    order_view = lookup_order(conn, order_id, claim["principal_id"])
    if not order_view["visible"]:
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        trace.add("decision", {"status": "escalated", "reason": order_view["reason"]})
        return _finish(conn, claim_id, seed, "escalated", 0, budget, trace, order_view["reason"])
    order = order_view["order"]  # allowlisted fields only
    trace.add("order", order)

    # Step 4: quote from the DB row and current policies. Ticket delay numbers are ignored.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    trace.add("quote", quote)
    proposal = int(quote["amount_vnd"])

    # Step 5: nothing owed -> denied. The host is not called, so no audit row.
    if proposal <= 0:
        complete(budget, seed=seed, purpose="draft", prompt="denied")
        trace.add("decision", {"status": "denied", "reason": quote["reason"]})
        return _finish(conn, claim_id, seed, "denied", 0, budget, trace, quote["reason"])

    # Step 6: hand the FULL quote to the host. It checks approval, per-order cap and
    # idempotency. Do not subtract earlier refunds here. InjectedCrash must propagate.
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

    # Step 7: success.
    return _finish(conn, claim_id, seed, "resolved", proposal, budget, trace, None)
