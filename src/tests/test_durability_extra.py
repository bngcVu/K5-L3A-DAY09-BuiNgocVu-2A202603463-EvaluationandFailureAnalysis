"""Unit tests for Ledger and Durability mechanisms.

Covers:
1. Idempotency on repeated claim runs with identical quote and conflict on different quote.
2. Approval binding: mismatch claim, missing, revoked, expired, and non-positive approvals.
3. Per-order refund cap: partial delta top-up and rejection when order cap is exhausted.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lab8.db import connect
from lab8.durability import (
    committed_audit_count,
    get_refund,
    idempotency_key,
    issue_refund,
)
from lab8.policy import order_refunded_vnd


def _insert_order(
    conn: sqlite3.Connection,
    order_id: str,
    *,
    paid_vnd: int = 250000,
    principal_id: str = "P-100",
) -> None:
    conn.execute(
        """
        INSERT INTO orders (
            order_id, principal_id, status, delay_days, shipping_fee_vnd,
            paid_vnd, damage_verified, carrier, phone, address, internal_note, item_name
        ) VALUES (?, ?, 'delivered', 3, 30000, ?, 1, 'VNPost', '0901234567', 'Hanoi', '', 'Sample item')
        """,
        (order_id, principal_id, paid_vnd),
    )
    conn.commit()


def _insert_claim(
    conn: sqlite3.Connection,
    claim_id: str,
    order_id: str,
    approval_id: str | None = None,
    *,
    principal_id: str = "P-100",
) -> None:
    conn.execute(
        """
        INSERT INTO claims (
            claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id
        ) VALUES (?, ?, ?, 'ticket inquiry', 'CANARY_SECRET_EXTRA_TEST', '{}', ?)
        """,
        (claim_id, principal_id, order_id, approval_id),
    )
    conn.commit()


def _insert_approval(
    conn: sqlite3.Connection,
    approval_id: str,
    claim_id: str,
    approved_vnd: int = 150000,
    *,
    status: str = "valid",
    expires_at: str = "2027-12-31",
) -> None:
    conn.execute(
        """
        INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (approval_id, claim_id, approved_vnd, status, expires_at),
    )
    conn.commit()


def _get_denials(conn: sqlite3.Connection, claim_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT details_json FROM audit_events
        WHERE claim_id = ? AND event_type = 'policy_denied'
        """,
        (claim_id,),
    ).fetchall()
    return [json.loads(row["details_json"]) for row in rows]


def test_idempotency_same_claim_twice(public_db: Path) -> None:
    """Calling issue_refund twice for the same claim must produce exactly one ledger row and one audit."""
    conn = connect(public_db)
    claim_id = "C-001"
    quote_vnd = 35000

    first = issue_refund(conn, claim_id, quote_vnd)
    second = issue_refund(conn, claim_id, quote_vnd)

    effect = get_refund(conn, claim_id)
    audits = committed_audit_count(conn, claim_id)

    ledger_rows = conn.execute(
        "SELECT COUNT(*) AS count FROM refund_ledger WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()["count"]
    conn.close()

    assert first["ok"] is True
    assert first["reason"] == "committed"
    assert second["ok"] is True
    assert second["reason"] == "idempotent_replay"
    assert second["conflict"] is False

    assert effect is not None
    assert int(effect["amount_vnd"]) == quote_vnd
    assert effect["idempotency_key"] == idempotency_key(claim_id)
    assert ledger_rows == 1
    assert audits == 1


def test_idempotency_retry_different_amount_conflicts(public_db: Path) -> None:
    """Calling issue_refund with a different quote than committed must flag conflict and keep original."""
    conn = connect(public_db)
    claim_id = "C-001"
    initial_quote = 35000
    conflicting_quote = 15000

    first = issue_refund(conn, claim_id, initial_quote)
    assert first["ok"] is True

    conflict_res = issue_refund(conn, claim_id, conflicting_quote)
    effect = get_refund(conn, claim_id)

    conflict_audits = conn.execute(
        """
        SELECT COUNT(*) AS count FROM audit_events
        WHERE claim_id = ? AND event_type = 'amount_conflict'
        """,
        (claim_id,),
    ).fetchone()["count"]
    conn.close()

    assert conflict_res["ok"] is False
    assert conflict_res["conflict"] is True
    assert conflict_res["reason"] == "amount_conflict"

    assert effect is not None
    assert int(effect["amount_vnd"]) == initial_quote
    assert conflict_audits == 1


def test_approval_mismatch_denied(public_db: Path) -> None:
    """Calling issue_refund when approval_id belongs to another claim must be rejected."""
    conn = connect(public_db)
    order_id = "O-EXTRA-MISMATCH"
    claim_id = "C-EXTRA-MISMATCH"
    _insert_order(conn, order_id, paid_vnd=100000)
    # A-001 is already assigned to C-001 in seeded data
    _insert_claim(conn, claim_id, order_id, approval_id="A-001")

    outcome = issue_refund(conn, claim_id, 35000)
    effect = get_refund(conn, claim_id)
    denials = _get_denials(conn, claim_id)
    conn.close()

    assert outcome["ok"] is False
    assert outcome["reason"] == "approval_claim_mismatch"
    assert effect is None
    assert any(d.get("reason") == "approval_claim_mismatch" for d in denials)


def test_approval_missing_revoked_expired_and_non_positive(public_db: Path) -> None:
    """Missing, revoked, expired, or non-positive approvals must be denied with audit event."""
    conn = connect(public_db)

    # 1. Missing approval
    _insert_order(conn, "O-EXTRA-MISSING", paid_vnd=100000)
    _insert_claim(conn, "C-EXTRA-MISSING", "O-EXTRA-MISSING", approval_id=None)
    out_missing = issue_refund(conn, "C-EXTRA-MISSING", 30000)
    assert out_missing["ok"] is False
    assert out_missing["reason"] == "missing_approval"
    assert any(d.get("reason") == "missing_approval" for d in _get_denials(conn, "C-EXTRA-MISSING"))

    # 2. Revoked approval
    _insert_order(conn, "O-EXTRA-REVOKED", paid_vnd=100000)
    _insert_claim(conn, "C-EXTRA-REVOKED", "O-EXTRA-REVOKED", approval_id="A-EXTRA-REVOKED")
    _insert_approval(conn, "A-EXTRA-REVOKED", "C-EXTRA-REVOKED", 30000, status="revoked")
    out_revoked = issue_refund(conn, "C-EXTRA-REVOKED", 30000)
    assert out_revoked["ok"] is False
    assert out_revoked["reason"] == "approval_revoked"
    assert any(d.get("reason") == "approval_revoked" for d in _get_denials(conn, "C-EXTRA-REVOKED"))

    # 3. Expired approval
    _insert_order(conn, "O-EXTRA-EXPIRED", paid_vnd=100000)
    _insert_claim(conn, "C-EXTRA-EXPIRED", "O-EXTRA-EXPIRED", approval_id="A-EXTRA-EXPIRED")
    _insert_approval(conn, "A-EXTRA-EXPIRED", "C-EXTRA-EXPIRED", 30000, expires_at="2020-01-01")
    out_expired = issue_refund(conn, "C-EXTRA-EXPIRED", 30000)
    assert out_expired["ok"] is False
    assert out_expired["reason"] == "approval_expired"
    assert any(d.get("reason") == "approval_expired" for d in _get_denials(conn, "C-EXTRA-EXPIRED"))

    # 4. Non-positive amount (approved_vnd = 0)
    _insert_order(conn, "O-EXTRA-ZERO", paid_vnd=100000)
    _insert_claim(conn, "C-EXTRA-ZERO", "O-EXTRA-ZERO", approval_id="A-EXTRA-ZERO")
    _insert_approval(conn, "A-EXTRA-ZERO", "C-EXTRA-ZERO", approved_vnd=0)
    out_zero = issue_refund(conn, "C-EXTRA-ZERO", 30000)
    assert out_zero["ok"] is False
    assert out_zero["reason"] == "non_positive_amount"
    assert any(d.get("reason") == "non_positive_amount" for d in _get_denials(conn, "C-EXTRA-ZERO"))

    # Verify no ledger rows created for any of these claims
    for cid in ("C-EXTRA-MISSING", "C-EXTRA-REVOKED", "C-EXTRA-EXPIRED", "C-EXTRA-ZERO"):
        assert get_refund(conn, cid) is None

    conn.close()


def test_order_cap_partial_and_exhausted_refund(public_db: Path) -> None:
    """Host must subtract earlier refunds on the same order and reject when total entitlement cap is reached."""
    conn = connect(public_db)
    order_id = "O-EXTRA-CAP-FLOW"
    _insert_order(conn, order_id, paid_vnd=300000)

    # Claim 1: Initial shipping refund 30,000 VND
    claim1 = "C-EXTRA-CAP-1"
    app1 = "A-EXTRA-CAP-1"
    _insert_claim(conn, claim1, order_id, approval_id=app1)
    _insert_approval(conn, app1, claim1, approved_vnd=30000)

    res1 = issue_refund(conn, claim1, 30000)
    assert res1["ok"] is True
    assert res1["reason"] == "committed"
    assert int(get_refund(conn, claim1)["amount_vnd"]) == 30000
    assert order_refunded_vnd(conn, order_id) == 30000

    # Claim 2: Damage refund full quote 150,000 VND.
    # Host subtracts 30,000 already refunded -> commits delta of 120,000 VND.
    claim2 = "C-EXTRA-CAP-2"
    app2 = "A-EXTRA-CAP-2"
    _insert_claim(conn, claim2, order_id, approval_id=app2)
    _insert_approval(conn, app2, claim2, approved_vnd=150000)

    res2 = issue_refund(conn, claim2, 150000)
    assert res2["ok"] is True
    assert res2["reason"] == "committed"
    assert int(get_refund(conn, claim2)["amount_vnd"]) == 120000
    # Order cumulative refund reaches 150,000 (never exceeds max entitlement)
    assert order_refunded_vnd(conn, order_id) == 150000

    # Claim 3: Another claim trying to claim 150,000 on the same order when cap is already exhausted.
    claim3 = "C-EXTRA-CAP-3"
    app3 = "A-EXTRA-CAP-3"
    _insert_claim(conn, claim3, order_id, approval_id=app3)
    _insert_approval(conn, app3, claim3, approved_vnd=150000)

    res3 = issue_refund(conn, claim3, 150000)
    assert res3["ok"] is False
    assert res3["reason"] == "order_already_refunded"
    assert get_refund(conn, claim3) is None
    assert any(d.get("reason") == "order_already_refunded" for d in _get_denials(conn, claim3))
    # Order total remains 150,000
    assert order_refunded_vnd(conn, order_id) == 150000

    conn.close()

