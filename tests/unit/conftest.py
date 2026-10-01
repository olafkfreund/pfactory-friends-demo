"""Make the generated source-inspection tests runnable where they live.

These tests read ``app/api/app/store.py`` as text and assert on its contents.
As generated they resolved it as ``<three parents up>/.worktree/app/api/...``,
which is TFactory's verify-sandbox layout -- so once committed to this
repository they raised ``FileNotFoundError`` on every run, permanently. They
were unrunnable in the only place they are stored.

``source_path`` finds the file by walking up to the repository root instead, so
the same test works in the sandbox and in the repo. Nothing about what they
assert changes.
"""

from __future__ import annotations

import pathlib

import pytest


def _find(relative: str) -> pathlib.Path:
    """Locate *relative* by walking up from this file to the repo root.

    Checks the sandbox's ``.worktree/`` prefix first so a verify run keeps
    reading exactly the tree it checked out, then the plain repo layout.
    """
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        for candidate in (parent / ".worktree" / relative, parent / relative):
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        f"{relative} not found walking up from {here}. These tests read it as "
        "text; without it they cannot verify anything, which is a different "
        "thing from the assertion failing."
    )


@pytest.fixture(scope="session")
def store_source() -> str:
    return _find("app/api/app/store.py").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def store_path() -> pathlib.Path:
    return _find("app/api/app/store.py")
