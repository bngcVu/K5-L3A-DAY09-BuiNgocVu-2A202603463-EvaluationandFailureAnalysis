"""M1 trace cases turned into regression tests (docs/trace_case.md).

Each test replays one claim@seed with MockLLM on a temp store (lab9.trace_case.investigate),
asserts the FIRST wrong step on the buggy shape, and asserts the same step is clean on `fixed`.
"""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def investigate():
    # The Lab 8 CI (ci.yml) installs only requirements.txt and runs `-m student -k swarm`, which
    # selects the swarm case below; lab9 needs requirements-lab9.txt, so skip there instead of erroring.
    pytest.importorskip("pydantic_evals")
    from lab9.trace_case import investigate

    return investigate


def _kinds(trial):
    return [e.get("kind") for e in trial["events"]]


def _first(trial, kind):
    """(1-based step, payload) of the first event of this kind, as trace_case numbers it."""
    for i, e in enumerate(trial["events"], 1):
        if e.get("kind") == kind:
            return i, e.get("payload")
    return None, None


def no_pre_deduction(trial, label):
    """FM-05 guard: the amount handed to the host must be the full quote, and the ledger must
    hold the label amount (host does the per-order cap itself)."""
    step, payload = _first(trial, "proposal")
    proposal_ok = step is None or payload["amount_vnd"] == label["proposal_amount"]
    return proposal_ok and trial["snapshot"]["refund_vnd"] == label["refund_vnd"]


def test_fm05_c014_first_wrong_step_is_proposal(investigate):
    case = investigate("seeded_regression", "C-014", 11)
    t, label = case["trial"], case["label"]
    step, payload = _first(t, "proposal")
    hist_step, hist = _first(t, "refund_history")
    assert hist_step == 4 and hist["refunded_vnd"] == 30000      # step 4 reads history correctly
    assert step == 5 and payload["amount_vnd"] == 120000         # step 5: 150.000 - 30.000 pre-deducted
    assert t["snapshot"]["refund_vnd"] == 90000                  # host subtracts again -> 90.000
    assert not no_pre_deduction(t, label)


def test_fm05_c014_fixed_passes_same_guard(investigate):
    case = investigate("fixed", "C-014", 11)
    t, label = case["trial"], case["label"]
    assert "proposal" not in _kinds(t)
    assert no_pre_deduction(t, label)
    assert t["lab8_pass"], t["lab8_reason"]


@pytest.mark.parametrize("shape, seed, overridden", [
    ("swarm", 55, True),               # reference weakness seed % 5 == 0
    ("seeded_regression", 11, True),
    ("fixed", 55, False),
])
def test_fm03_c002_db_fact_kept(investigate, shape, seed, overridden):
    t = investigate(shape, "C-002", seed)["trial"]
    step, payload = _first(t, "model_override")
    if overridden:
        assert step == 3 and payload == {"delay_days": 5}         # ticket "5 ngày" beats DB delay_days=2
        assert t["snapshot"]["refund_vnd"] == 20000 and not t["lab8_pass"]
    else:
        assert step is None
        assert t["result"]["status"] == "denied" and t["lab8_pass"]
