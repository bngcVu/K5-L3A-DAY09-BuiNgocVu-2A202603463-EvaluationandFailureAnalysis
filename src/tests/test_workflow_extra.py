"""Extra tests for shape A (workflow): the ticket is data, never a source of truth."""

from __future__ import annotations

import json
import sqlite3

import pytest

from lab8.durability import InjectedCrash
from lab8.shapes import workflow
from tests.conftest import CLAIMS

LEAK_NEEDLES = (
    "CANARY_SECRET",
    "Bearer",
    "0901000107",
    "CANARY_INTERNAL_O107",
    "12 Le Loi Q1",
)


def _q(store, sql: str, *args):
    conn = sqlite3.connect(store)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _ledger(store, claim_id: str) -> list[int]:
    return [r[0] for r in _q(store, "SELECT amount_vnd FROM refund_ledger WHERE claim_id = ?", claim_id)]


def _audit_count(store, claim_id: str, event_type: str) -> int:
    return _q(
        store,
        "SELECT COUNT(*) FROM audit_events WHERE claim_id = ? AND event_type = ?",
        claim_id,
        event_type,
    )[0][0]


def _trace_text(result) -> str:
    with open(result.trace_path, encoding="utf-8") as fh:
        return fh.read()


# --- whole public matrix, every seed --------------------------------------


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
@pytest.mark.parametrize("case", CLAIMS, ids=[c["matrix_id"] for c in CLAIMS])
def test_public_matrix_matches_expected(public_db, case, seed):
    exp = case["expected"]
    result = workflow.run_claim(case["claim_id"], seed=seed, store_path=str(public_db))
    assert result.status == exp["status"]
    assert result.proposal_amount == exp["proposal_amount"]
    assert sum(_ledger(public_db, case["claim_id"])) == exp["refund_vnd"]
    assert (_audit_count(public_db, case["claim_id"], "policy_denied") > 0) == exp["policy_denied"]
    raw = _trace_text(result)
    for needle in exp["forbid_substrings"]:
        assert needle not in raw


# --- ticket is data --------------------------------------------------------


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_ticket_delay_is_ignored_on_every_seed(public_db, seed):
    # C-002 says "tre 5 ngay" but the order row does not qualify. Seed 55 is the one
    # where the reference swarm trusts the ticket; the workflow must not.
    result = workflow.run_claim("C-002", seed=seed, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert _ledger(public_db, "C-002") == []


def test_ignore_policy_instruction_is_just_data(public_db):
    result = workflow.run_claim("C-009", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert _ledger(public_db, "C-009") == []


def test_old_policy_clause_in_ticket_is_ignored(public_db):
    # C-006 quotes SHIP-LATE-OLD and "tre 2 ngay": no refund.
    result = workflow.run_claim("C-006", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert _audit_count(public_db, "C-006", "policy_denied") == 0


# --- branches and boundaries ----------------------------------------------


def test_missing_order_id_needs_info_and_no_ledger(public_db):
    result = workflow.run_claim("C-004", seed=11, store_path=str(public_db))
    assert result.status == "needs_info"
    assert result.proposal_amount == 0
    assert result.error_reason == "missing_order_id"
    assert _ledger(public_db, "C-004") == []


def test_wrong_principal_escalates_without_leaking_order(public_db):
    result = workflow.run_claim("C-005", seed=11, store_path=str(public_db))
    assert result.status == "escalated"
    assert result.proposal_amount == 0
    assert result.error_reason == "outside_principal_scope"
    raw = _trace_text(result)
    for needle in LEAK_NEEDLES:
        assert needle not in raw
    assert _ledger(public_db, "C-005") == []


def test_big_damage_quote_wins_over_ship_fee(public_db):
    # C-003: ship + damage both qualify, one refund at the larger number (150.000).
    result = workflow.run_claim("C-003", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert _ledger(public_db, "C-003") == [150000]


def test_denied_by_shape_does_not_call_host(public_db):
    # Quote 0 -> the shape denies by itself, so no audit event of any kind.
    result = workflow.run_claim("C-002", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert _audit_count(public_db, "C-002", "policy_denied") == 0
    assert result.committed_audit_count == 0


def test_order_cap_denied_keeps_full_quote(public_db):
    # T13: order already refunded in full -> denied, proposal stays the full quote.
    result = workflow.run_claim("C-013", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 35000
    assert _audit_count(public_db, "C-013", "policy_denied") == 1


def test_order_cap_pays_only_the_difference(public_db):
    # T14: shape passes the FULL 150.000 quote; the host subtracts the 30.000 already paid.
    result = workflow.run_claim("C-014", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert _ledger(public_db, "C-014") == [120000]


def test_approval_lower_than_quote_is_capped_by_host(public_db):
    # T08: approval 20.000 < quote 35.000.
    result = workflow.run_claim("C-008", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    assert _ledger(public_db, "C-008") == [20000]


def test_unknown_claim_fails_without_raising(public_db):
    result = workflow.run_claim("C-NOPE", seed=11, store_path=str(public_db))
    assert result.status == "failed"
    assert result.proposal_amount == 0
    assert result.error_reason == "unknown_claim"


# --- idempotency and crash -------------------------------------------------


def test_rerun_same_claim_keeps_single_ledger_row(public_db):
    first = workflow.run_claim("C-001", seed=11, store_path=str(public_db))
    second = workflow.run_claim("C-001", seed=22, store_path=str(public_db))
    assert first.status == second.status == "resolved"
    assert _ledger(public_db, "C-001") == [35000]
    assert second.committed_audit_count == 1


@pytest.mark.parametrize(
    "crash_at",
    ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"],
)
def test_crash_then_resume_has_exactly_one_refund(public_db, crash_at):
    with pytest.raises(InjectedCrash):
        workflow.run_claim("C-012", seed=11, store_path=str(public_db), crash_at=crash_at)
    resumed = workflow.run_claim("C-012", seed=11, store_path=str(public_db))
    assert resumed.status == "resolved"
    assert _ledger(public_db, "C-012") == [35000]
    assert _audit_count(public_db, "C-012", "refund_committed") == 1


# --- trace contract --------------------------------------------------------


@pytest.mark.parametrize("case", CLAIMS, ids=[c["matrix_id"] for c in CLAIMS])
def test_trace_contract_on_every_branch(public_db, case):
    result = workflow.run_claim(case["claim_id"], seed=11, store_path=str(public_db))
    data = json.loads(_trace_text(result))
    assert data["run_id"] == result.run_id
    assert isinstance(data["events"], list) and data["events"]


def test_trace_is_written_when_crash_is_injected(public_db):
    with pytest.raises(InjectedCrash):
        workflow.run_claim(
            "C-012", seed=11, store_path=str(public_db), crash_at="after_effect_before_checkpoint"
        )
    from lab8.schemas import make_run_id
    from lab8.trace import Trace

    assert Trace(make_run_id("workflow", "C-012", 11)).path.exists()
