"""AC#3: An account whose stated age is under 16 is refused at creation, and
the refusal names age as the reason.

Target: app/api/app/store.py::ProfileStore.save

ProfileStore.save raises ValueError("age_below_minimum") when profile.age is
below MIN_AGE (16) — see app/api/app/store.py, MIN_AGE and the save() method's
own docstring, which documents "age_below_minimum" as the reason code for
this refusal. Age 16 itself (the boundary) must be accepted.
"""

from __future__ import annotations

import pytest

from app.domain import Profile
from app.store import MIN_AGE, ProfileStore


def _profile(profile_id: str, age: int) -> Profile:
    return Profile(id=profile_id, display_name=f"User {profile_id}", age=age)


class TestUnder16AgeRefused:
    """AC#3: age below 16 is refused with a reason naming age; age 16 is accepted."""

    def test_age_15_is_refused_with_reason_naming_age(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="age_below_minimum") as exc_info:
            store.save(_profile("teen-15", age=15))
        assert "age" in str(exc_info.value)
        # The refused profile must not have been persisted.
        assert store.find("teen-15") is None

    def test_age_0_is_refused_with_reason_naming_age(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="age_below_minimum") as exc_info:
            store.save(_profile("infant", age=0))
        assert "age" in str(exc_info.value)
        assert store.find("infant") is None

    def test_age_one_below_minimum_is_refused(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="age_below_minimum"):
            store.save(_profile("almost", age=MIN_AGE - 1))
        assert store.find("almost") is None

    def test_age_16_is_accepted(self) -> None:
        store = ProfileStore()
        store.save(_profile("sixteen", age=16))
        saved = store.find("sixteen")
        assert saved is not None
        assert saved.age == 16

    def test_age_exactly_min_age_is_accepted(self) -> None:
        assert MIN_AGE == 16
        store = ProfileStore()
        store.save(_profile("min-age", age=MIN_AGE))
        saved = store.find("min-age")
        assert saved is not None
        assert saved.age == MIN_AGE
