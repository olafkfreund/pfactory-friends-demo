"""AC#10: Blocking is symmetric: after either person blocks the other,
neither can discover, request, nor message the other, and the API refuses
both directions with the same reason.

This file targets the single shared predicate, app.store.may_contact, and
proves that it enforces the block symmetrically regardless of which side
issued the block and regardless of the order the two ids are passed in.

app.store.may_contact(store, a, b) returns:
    not (store.is_blocked(blocker_id=a, blocked_id=b)
         or store.is_blocked(blocker_id=b, blocked_id=a))

so a block recorded in either direction must make may_contact(store, a, b)
AND may_contact(store, b, a) both return False. A one-directional
implementation (`not store.is_blocked(a, b)` only) would let the blocked
party still "contact" the blocker when queried in the reversed argument
order -- that is exactly the asymmetry this test suite is here to catch.
"""

from __future__ import annotations

import pytest

from app.store import ProfileStore, may_contact


# ---------------------------------------------------------------------------
# Baseline: no block recorded
# ---------------------------------------------------------------------------


def test_may_contact_true_when_neither_has_blocked() -> None:
    """Two strangers with no block record may contact each other in either order."""
    store = ProfileStore()
    assert may_contact(store, "alice", "bob") is True
    assert may_contact(store, "bob", "alice") is True


# ---------------------------------------------------------------------------
# AC#10: symmetry after either side blocks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "blocker,blocked",
    [
        pytest.param("alice", "bob", id="alice_blocks_bob"),
        pytest.param("bob", "alice", id="bob_blocks_alice"),
    ],
)
def test_may_contact_false_both_query_orders_after_either_side_blocks(
    blocker: str, blocked: str
) -> None:
    """Whichever of the two people places the block, may_contact(store, a, b)
    returns False whether queried as (blocker, blocked) or (blocked, blocker).

    This is the direct proof of AC#10: the single may_contact predicate
    refuses contact symmetrically no matter who blocked whom, and no matter
    which of the two ids is passed as the first argument.
    """
    store = ProfileStore()
    store.block(blocker, blocked)

    # Query in the natural (blocker, blocked) order.
    assert may_contact(store, blocker, blocked) is False
    # Query in the reversed (blocked, blocker) order -- the symmetry check.
    assert may_contact(store, blocked, blocker) is False


def test_may_contact_false_after_a_blocks_b_regardless_of_query_order() -> None:
    """Explicit A-blocks-B case: neither may_contact(store, a, b) nor
    may_contact(store, b, a) permits contact (AC#10)."""
    store = ProfileStore()
    store.block("alice", "bob")

    assert may_contact(store, "alice", "bob") is False
    assert may_contact(store, "bob", "alice") is False


def test_may_contact_false_after_b_blocks_a_regardless_of_query_order() -> None:
    """Explicit B-blocks-A case (the reversed block direction): neither
    query order permits contact, proving the predicate is not merely
    checking the first argument against the second (AC#10)."""
    store = ProfileStore()
    store.block("bob", "alice")

    assert may_contact(store, "alice", "bob") is False
    assert may_contact(store, "bob", "alice") is False


def test_may_contact_refusal_identical_for_both_block_directions() -> None:
    """The boolean outcome of may_contact is the same (False) whether alice
    blocked bob or bob blocked alice -- the API cannot be told apart from
    the outcome alone, which is what "same reason" in AC#10 requires at the
    predicate level."""
    store_a_blocks_b = ProfileStore()
    store_a_blocks_b.block("alice", "bob")

    store_b_blocks_a = ProfileStore()
    store_b_blocks_a.block("bob", "alice")

    outcome_when_a_blocked = may_contact(store_a_blocks_b, "alice", "bob")
    outcome_when_b_blocked = may_contact(store_b_blocks_a, "alice", "bob")

    assert outcome_when_a_blocked is False
    assert outcome_when_b_blocked is False
    assert outcome_when_a_blocked == outcome_when_b_blocked


def test_may_contact_unrelated_third_party_unaffected_by_block() -> None:
    """A block between alice and bob does not affect may_contact for an
    unrelated third party, confirming the predicate is scoped to the pair
    named in the block record."""
    store = ProfileStore()
    store.block("alice", "bob")

    assert may_contact(store, "alice", "carol") is True
    assert may_contact(store, "carol", "alice") is True
    assert may_contact(store, "bob", "carol") is True
