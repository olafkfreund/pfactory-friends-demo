"""Data-retention policy for MyFriends — single source of truth (C16).

All retention durations are defined here and nowhere else in the backend.
Any code that needs to know how long a category of data is kept must import
from this module rather than hard-coding a number.

Policy summary
--------------
| Category                        | Retention period                      |
|---------------------------------|---------------------------------------|
| Messages                        | 24 months from account closure        |
| Blocks                          | 24 months after closure               |
| Reports                         | 24 months after closure               |
| Everything else (profile, tags, | 30 days after account deletion        |
|   connections, activities, …)   |                                       |

Rationale
---------
- Messages, blocks, and reports must be kept for 24 months post-closure so
  that trust-and-safety teams can investigate abuse that is reported after
  an account is deleted.
- All other personal data (display name, bio, age, interest tags, activity
  tags, availability flags, connection requests) is removed within 30 days
  of deletion in line with the platform's deletion SLA.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """Immutable retention-period descriptor.

    All durations are expressed in calendar months.
    A "month" is defined as 30 days for calculation purposes (P2 / legal).
    """

    # Kept for 24 calendar months from account closure so trust-and-safety
    # can audit post-deletion abuse reports (C16).
    messages_months: int

    # Blocks and reports are kept together — same 24-month post-closure window.
    blocks_months: int
    reports_months: int

    # Everything else: profile row, interest tags, activity tags, connections,
    # availability flags.  Purged within 30 days of deletion (one calendar month
    # in practical terms; 30 days is the SLA).
    other_days: int


# ---------------------------------------------------------------------------
# The canonical policy instance — import this object everywhere.
# ---------------------------------------------------------------------------

RETENTION_POLICY: RetentionPolicy = RetentionPolicy(
    messages_months=24,
    blocks_months=24,
    reports_months=24,
    other_days=30,
)
