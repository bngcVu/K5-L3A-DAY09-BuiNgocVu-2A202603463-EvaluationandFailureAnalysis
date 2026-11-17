import json
from contextlib import closing
from pathlib import Path

from lab8.db import connect
from lab8.durability import get_refund
from lab8.handoff import ALLOWED_FIELDS
from lab8.shapes import orchestrator
from tests.conftest import BY_ID, WORLD


def test_orchestrator_handoff_is_read_only_and_trace_is_safe(public_db, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    claim = BY_ID["C-001"]
    order = next(order for order in WORLD["orders"] if order["order_id"] == claim["order_id"])
    ticket_marker = "synthetic ticket text reserved for this test"
    with closing(connect(public_db)) as conn:
        conn.execute("UPDATE claims SET ticket = ? WHERE claim_id = ?", (ticket_marker, claim["claim_id"]))
        conn.commit()

    handoffs = []
    investigate = orchestrator.run_readonly_investigators

    def check_investigator(conn, budget, handoff, principal_id):
        assert set(handoff) == ALLOWED_FIELDS
        assert handoff["facts"] == {}
        assert handoff["allowed_tools"] == ["lookup_order"]
        assert handoff["principal_scope"] == "owner_order_only"
        assert principal_id == claim["principal_id"]
        assert get_refund(conn, claim["claim_id"]) is None
        handoffs.append(handoff)
        result = investigate(conn, budget, handoff, principal_id)
        assert get_refund(conn, claim["claim_id"]) is None
        return result

    monkeypatch.setattr(orchestrator, "run_readonly_investigators", check_investigator)
    result = orchestrator.run_claim(claim["claim_id"], seed=11, store_path=str(public_db))

    assert result.status == "resolved"
    assert len(result.refund_effects) == 1
    assert len(handoffs) == 1
    trace_text = Path(result.trace_path).read_text(encoding="utf-8")
    trace = json.loads(trace_text)
    assert trace["run_id"] == result.run_id
    assert [event["payload"] for event in trace["events"] if event["kind"] == "handoff"] == handoffs

    captured = capsys.readouterr()
    output = "\n".join((trace_text, json.dumps(result.as_dict(), ensure_ascii=False), captured.out, captured.err))
    sensitive_values = [
        "CANARY_SECRET_",
        ticket_marker,
        *claim["raw_headers"].values(),
        *(order[field] for field in ("phone", "address", "internal_note", "item_name")),
    ]
    for value in sensitive_values:
        assert value not in output


def test_orchestrator_unknown_claim_has_a_trace(public_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = orchestrator.run_claim("C-NOT-FOUND", seed=11, store_path=str(public_db))

    assert (result.status, result.error_reason) == ("failed", "unknown_claim")
    assert not result.refund_effects
    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert trace["run_id"] == result.run_id
    assert trace["events"] == [{"kind": "decision", "payload": {"status": "failed", "reason": "unknown_claim"}}]
