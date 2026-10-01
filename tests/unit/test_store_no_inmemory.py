# AC#4: no in-process dictionary holding the only copy; data must be in Postgres.
#
# Subtask: store-no-inmemory-dict
# Target:  app/api/app/store.py::bootstrap_schema
# Criterion: the store module defines no module-level Python dicts or lists
#            used to hold profiles, connections, messages, blocks, or reports.
#
# Implementation note:
#   This test uses Python's ast module to inspect the store source statically.
#   Importing store directly would require psycopg3 and DATABASE_URL; parsing
#   the source avoids both and still proves the structural criterion.

from __future__ import annotations

import ast
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Locate store.py relative to this test file
#   tests/unit/test_store_no_inmemory.py
#     -> tests/unit/
#     -> tests/
#     -> spec_dir (026-myfriends-remediation-verify/)
#     -> spec_dir/.worktree/app/api/app/store.py
# ---------------------------------------------------------------------------

_STORE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / ".worktree"
    / "app"
    / "api"
    / "app"
    / "store.py"
)

_ENTITY_NAMES = frozenset({
    "profiles",
    "connections",
    "messages",
    "blocks",
    "reports",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_store() -> ast.Module:
    """Return the parsed AST of store.py."""
    source = _STORE_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(_STORE_PATH))


def _module_level_assigns(tree: ast.Module) -> list[tuple[list[str], ast.expr, int]]:
    """Yield (names, value_node, lineno) for every top-level assignment."""
    results = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            results.append((names, node.value, node.lineno))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            name = node.target.id if isinstance(node.target, ast.Name) else ""
            results.append(([name], node.value, node.lineno))
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_store_source_file_exists_and_parses():
    """store.py must exist at the expected path and be syntactically valid."""
    assert _STORE_PATH.exists(), (
        f"store.py not found at {_STORE_PATH}; cannot verify AC#4"
    )
    # parse must succeed without raising SyntaxError
    _parse_store()


def test_store_no_module_level_dict_holding_entity_data():
    """No module-level dict literal is assigned to an entity-related name.

    AC#4 requires profiles, connections, messages, blocks and reports to live
    in Postgres.  A module-level assignment like ``profiles = {}`` would mean
    data lives only in the process and is lost on restart.
    """
    tree = _parse_store()
    violations: list[str] = []

    for names, value, lineno in _module_level_assigns(tree):
        if isinstance(value, ast.Dict):
            matching = [n for n in names if n.lower() in _ENTITY_NAMES]
            for name in matching:
                violations.append(
                    f"  line {lineno}: {name} = {{...}}  "
                    f"(module-level dict named after entity type)"
                )

    assert violations == [], (
        "store.py contains module-level dicts holding entity data — "
        "AC#4 requires all data to persist in Postgres:\n"
        + "\n".join(violations)
    )


def test_store_no_module_level_list_holding_entity_data():
    """No module-level list literal is assigned to an entity-related name.

    AC#4 requires profiles, connections, messages, blocks and reports to live
    in Postgres.  A module-level assignment like ``messages = []`` would mean
    data lives only in the process and is lost on restart.
    """
    tree = _parse_store()
    violations: list[str] = []

    for names, value, lineno in _module_level_assigns(tree):
        if isinstance(value, ast.List):
            matching = [n for n in names if n.lower() in _ENTITY_NAMES]
            for name in matching:
                violations.append(
                    f"  line {lineno}: {name} = [...]  "
                    f"(module-level list named after entity type)"
                )

    assert violations == [], (
        "store.py contains module-level lists holding entity data — "
        "AC#4 requires all data to persist in Postgres:\n"
        + "\n".join(violations)
    )


@pytest.mark.parametrize(
    "entity_name",
    sorted(_ENTITY_NAMES),
    ids=sorted(_ENTITY_NAMES),
)
def test_store_entity_name_not_a_plain_dict_or_list(entity_name: str):
    """Each entity-related name is not assigned a plain dict or list at module level.

    AC#4: 'no in-process dictionary holding the only copy'.  Parameterised over
    each entity type so failures name the exact entity that regressed.
    """
    tree = _parse_store()

    for names, value, lineno in _module_level_assigns(tree):
        lowered = [n.lower() for n in names]
        if entity_name in lowered:
            assert not isinstance(value, (ast.Dict, ast.List)), (
                f"store.py line {lineno}: '{entity_name}' is assigned a "
                f"{'dict' if isinstance(value, ast.Dict) else 'list'} literal — "
                f"AC#4 requires this entity's data to live in Postgres, not in memory."
            )


def test_store_has_no_module_level_plain_dict_at_all():
    """store.py must contain zero top-level plain dict ({}) assignments.

    The original defect was plain dicts at module scope; this broadens the
    guard to catch any dict literal introduced at module level, regardless
    of variable name, since entity data should always come from SQL queries.
    """
    tree = _parse_store()
    violations: list[str] = []

    for names, value, lineno in _module_level_assigns(tree):
        if isinstance(value, ast.Dict):
            violations.append(
                f"  line {lineno}: {', '.join(names) or '<annotated>'} = {{...}}"
            )

    assert violations == [], (
        "store.py has module-level plain dict assignments — "
        "AC#4 requires no in-process container to hold entity data:\n"
        + "\n".join(violations)
    )
