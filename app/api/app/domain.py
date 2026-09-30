"""Domain models for MyFriends (plan step 3).

Ported from lanes/kotlin-core as the specification of each rule.
The Kotlin core is the historical reference; this module is the single source
of truth for the backend rules going forward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class AgeBracket(str, Enum):
    """Age bracket used for discovery isolation (spec: compliance).

    An adult and a minor are never mutually discoverable — discovery only
    surfaces profiles in the same bracket as the searcher.
    """

    MINOR = "minor"  # 16–17
    ADULT = "adult"  # 18+


def age_bracket(age: int) -> AgeBracket:
    """Return the age bracket for the given age in years."""
    return AgeBracket.MINOR if age < 18 else AgeBracket.ADULT


class ConnectionStatus(str, Enum):
    """Lifecycle state of a connection between two users (AC#6)."""

    PENDING = "pending"
    ACCEPTED = "accepted"


class ReportReason(str, Enum):
    """Fixed list of reasons a person can choose when filing a report (AC#8).

    Ported verbatim from lanes/kotlin-core/src/main/kotlin/Report.kt.
    """

    SPAM = "spam"
    HARASSMENT = "harassment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    FAKE_PROFILE = "fake_profile"
    UNDERAGE_USER = "underage_user"
    OTHER = "other"


class ReportTargetKind(str, Enum):
    """Whether the report targets a person or a specific message (AC#8)."""

    USER = "user"
    MESSAGE = "message"


VALID_SEARCH_RADII: frozenset[int] = frozenset({1, 5, 10, 25})  # kilometres (AC#3)


@dataclass
class GeoLocation:
    """WGS-84 coordinate pair used for proximity-based discovery (AC#3).

    Location data is never shown to other users — only a town/city label is
    exposed (constitution P4, product-decisions.md decision 3). It is read
    only while the person is actively using the app (AC#12 / P4).

    Ported from lanes/kotlin-core/src/main/kotlin/GeoLocation.kt.
    """

    lat: float
    lon: float

    def distance_to(self, other: GeoLocation) -> float:
        """Return the great-circle distance in kilometres (haversine formula).

        Accuracy is within ~0.3 % over the 1–25 km distances this app uses,
        which is sufficient for the radius values in VALID_SEARCH_RADII.
        """
        lat1 = math.radians(self.lat)
        lat2 = math.radians(other.lat)
        dlat = math.radians(other.lat - self.lat)
        dlon = math.radians(other.lon - self.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return 6_371.0 * c  # mean Earth radius (WGS-84)


@dataclass
class Profile:
    """A user profile.

    Ported from lanes/kotlin-core/src/main/kotlin/Profile.kt.

    P1 (constitution, enforceable): all personal data kept here (display name,
    bio, age, location, interests, activities) is kept for as long as the
    account exists and deleted on account deletion.
    P4 (constitution, enforceable): location is read only while the person
    is actively using the app. It is stored here for proximity-based
    discovery and never surfaced to other users.
    """

    id: str
    display_name: str
    bio: str = ""
    interests: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    age: int = 18  # self-reported; must be >= MIN_AGE at save time
    open_to_friends: bool = False  # AC#2: off by default
    location: GeoLocation | None = None  # AC#12 / P4


@dataclass
class Connection:
    """A directed connection request from requester_id to recipient_id (AC#6).

    Ported from lanes/kotlin-core/src/main/kotlin/Connection.kt.
    """

    id: str
    requester_id: str
    recipient_id: str
    status: ConnectionStatus = ConnectionStatus.PENDING


@dataclass
class Message:
    """A message from sender_id to recipient_id (AC#6).

    Ported from lanes/kotlin-core/src/main/kotlin/Message.kt.
    """

    id: str
    sender_id: str
    recipient_id: str
    body: str


@dataclass
class DiscoveryResult:
    """A single discovery result with match score and shared tags (AC#4).

    Ported from lanes/kotlin-core/src/main/kotlin/DiscoveryResult.kt.
    shared_interests and shared_activities are sorted for deterministic display.
    """

    profile: Profile
    score: float
    shared_interests: list[str]
    shared_activities: list[str]


@dataclass
class Report:
    """A report filed by reporter_id against a target (AC#8).

    Ported from lanes/kotlin-core/src/main/kotlin/Report.kt.

    P5 (constitution, enforceable): every person-to-person surface ships with
    reporting in the same phase as the feature that creates the data.
    """

    id: str
    reporter_id: str
    target_id: str
    target_kind: ReportTargetKind
    reason: ReportReason
    additional_text: str = ""
