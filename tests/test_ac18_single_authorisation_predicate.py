"""AC#18: the authorisation decision for seeing, contacting, or messaging
another person is made in a single place in the backend.

``app.store.may_contact`` is that single place (see its docstring: "the fix
for #86, where the messaging path and the connection-request path disagreed
about what 'blocked' means"). Discovery (``discover``), connection requests
(``ConnectionStore.send_request``), and messaging (``MessageStore.send``) all
gate on it. This test drives a single blocked pair through all three surfaces
and asserts they agree with ``may_contact``'s outcome and with each other, so
no two surfaces can disagree about whether a pair may contact each other.
"""

from __future__ import annotations

import pytest

from app.domain import AgeAssuranceStatus, Profile
from app.store import ConnectionStore, MessageStore, ProfileStore, discover, may_contact


def _make_profile(profile_id: str) -> Profile:
    """Profile eligible for discovery: open_to_friends, adult, age-assurance passed."""
    return Profile(
        id=profile_id,
        display_name=profile_id,
        age=25,
        open_to_friends=True,
        age_assurance_status=AgeAssuranceStatus.PASSED,
    )


@pytest.fixture
def stores() -> tuple[ProfileStore, ConnectionStore, MessageStore]:
    profile_store = ProfileStore()
    profile_store.save(_make_profile("alice"))
    profile_store.save(_make_profile("bob"))
    connection_store = ConnectionStore(profile_store)
    message_store = MessageStore(profile_store, connection_store)
    return profile_store, connection_store, message_store


@pytest.mark.parametrize(
    "blocker_id,blocked_id",
    [("alice", "bob"), ("bob", "alice")],
    ids=["a_blocks_b", "b_blocks_a"],
)
def test_blocked_pair_refused_identically_across_discovery_request_and_message(
    stores: tuple[ProfileStore, ConnectionStore, MessageStore],
    blocker_id: str,
    blocked_id: str,
) -> None:
    """A block from either party is refused the same way on every surface.

    Regardless of which of the two blocks the other, may_contact(alice, bob)
    must be False in both argument orders, and discovery, send_request, and
    send.message must all refuse the pair -- not just the surface the blocker
    used. If any surface used its own ad hoc check instead of may_contact,
    it could disagree with the others here (the #86 regression).
    """
    profile_store, connection_store, message_store = stores

    # Establish an ACCEPTED connection *before* the block, so the messaging
    # surface's own "not_connected" / "connection_pending" refusals cannot
    # masquerade as the may_contact refusal under test.
    conn, request_reason = connection_store.send_request("alice", "bob")
    assert request_reason is None
    assert conn is not None
    accepted, accept_reason = connection_store.accept_request(conn.id, "bob")
    assert accepted is True
    assert accept_reason is None

    profile_store.block(blocker_id, blocked_id)

    # The single predicate itself refuses, in both argument orders.
    assert may_contact(profile_store, "alice", "bob") is False
    assert may_contact(profile_store, "bob", "alice") is False

    # Surface 1: discovery -- neither party may see the other once blocked.
    alice_profile = profile_store.find("alice")
    bob_profile = profile_store.find("bob")
    assert alice_profile is not None
    assert bob_profile is not None
    alice_results = discover(profile_store, alice_profile)
    bob_results = discover(profile_store, bob_profile)
    assert not any(r.profile.id == "bob" for r in alice_results)
    assert not any(r.profile.id == "alice" for r in bob_results)

    # Surface 2: connection requests -- neither direction may send a new
    # request once the pair is blocked.
    _, request_reason_ab = connection_store.send_request("alice", "bob")
    _, request_reason_ba = connection_store.send_request("bob", "alice")
    assert request_reason_ab == "blocked"
    assert request_reason_ba == "blocked"

    # Surface 3: messaging -- despite holding an ACCEPTED connection from
    # before the block, neither party can message the other now.
    _, message_reason_ab = message_store.send("alice", "bob", "hello")
    _, message_reason_ba = message_store.send("bob", "alice", "hi")
    assert message_reason_ab == "blocked"
    assert message_reason_ba == "blocked"


def test_unblocked_pair_permitted_identically_across_all_three_surfaces(
    stores: tuple[ProfileStore, ConnectionStore, MessageStore],
) -> None:
    """The positive control: with no block recorded, all three surfaces agree
    contact is permitted, proving the shared predicate isn't just failing
    open by coincidence.
    """
    profile_store, connection_store, message_store = stores

    assert may_contact(profile_store, "alice", "bob") is True
    assert may_contact(profile_store, "bob", "alice") is True

    alice_profile = profile_store.find("alice")
    bob_profile = profile_store.find("bob")
    assert alice_profile is not None
    assert bob_profile is not None
    alice_results = discover(profile_store, alice_profile)
    bob_results = discover(profile_store, bob_profile)
    assert any(r.profile.id == "bob" for r in alice_results)
    assert any(r.profile.id == "alice" for r in bob_results)

    conn, request_reason = connection_store.send_request("alice", "bob")
    assert request_reason is None
    assert conn is not None

    accepted, accept_reason = connection_store.accept_request(conn.id, "bob")
    assert accepted is True
    assert accept_reason is None

    message, message_reason = message_store.send("alice", "bob", "hello")
    assert message_reason is None
    assert message is not None
