# AC#5: Database credentials are read from the environment at runtime and appear
# nowhere in the repository or in any image.
#
# Subtask: database-credentials-not-hardcoded
# Target:  app/api/app/store.py::_database_url
#
# This test statically inspects store.py's AST to prove that:
#  1. No string literal in the module looks like a connection string that
#     embeds authentication credentials (e.g. "postgresql://user:pass@host/db").
#  2. The _database_url() function body reads from os.environ (not from a
#     hardcoded string literal assignment).
#  3. No variable named after a credential concept (password, passwd, secret,
#     db_url, database_url) is assigned a non-empty string literal at any scope.
#
# Strategy: parse the source with the `ast` module so neither psycopg3 nor a
# running DATABASE_URL is required — the check is purely structural.

from __future__ import annotations

import ast
import pathlib
import re
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Locate store.py relative to this test file:
#   tests/unit/test_no_hardcoded_credentials.py
#     -> tests/unit/
#     -> tests/
#     -> spec_dir (026-myfriends-remediation-verify/)
#     -> spec_dir/.worktree/app/api/app/store.py
# ---------------------------------------------------------------------------

from conftest import _find  # noqa: E402

_STORE_PATH = _find("app/api/app/store.py")

# Pattern that matches a connection-string URL containing embedded auth info,
# e.g. "postgresql://someuser:somepassword@host/db" or "postgres://u:p@h".
# A URL with no password section ("postgresql://host/db") is intentionally NOT
# matched — the criterion is about *credentials*, not mere protocol references.
_CONN_STRING_WITH_CREDS_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mariadb|mssql|sqlite)://"
    r"[^:@/\s]+:[^@/\s]+@",  # user:password@ present
    re.IGNORECASE,
)

# Variable names that, if assigned a non-empty string literal, are almost
# certainly a hardcoded credential.
_CREDENTIAL_VAR_NAMES = frozenset({
    "password",
    "passwd",
    "secret",
    "db_password",
    "db_passwd",
    "database_password",
    "db_url",
    "database_url",
    "connection_string",
    "conn_string",
    "dsn",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_store() -> ast.Module:
    """Return the parsed AST of store.py."""
    source = _STORE_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(_STORE_PATH))


def _all_string_constants(tree: ast.AST) -> Iterator[tuple[str, int]]:
    """Yield (string_value, lineno) for every string constant in the tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value, node.lineno


def _all_assignments(tree: ast.AST) -> Iterator[tuple[list[str], ast.expr, int]]:
    """Yield (names, value_node, lineno) for every assignment anywhere in the tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            yield names, node.value, node.lineno
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            name = node.target.id if isinstance(node.target, ast.Name) else ""
            yield [name], node.value, node.lineno


def _function_body_nodes(tree: ast.Module, func_name: str) -> list[ast.AST]:
    """Return all AST nodes inside the named top-level function."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return list(ast.walk(node))
    return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_store_source_file_exists_and_parses():
    """store.py must exist at the expected path and parse without errors."""
    assert _STORE_PATH.exists(), (
        f"store.py not found at {_STORE_PATH}; cannot verify AC#5"
    )
    _parse_store()  # raises SyntaxError if unparseable


def test_no_connection_string_with_embedded_credentials():
    """No string literal in store.py encodes credentials inside a URL.

    AC#5: credentials appear nowhere in the repository.  A string like
    "postgresql://admin:hunter2@postgres-host/mydb" would embed a password
    directly in the source and is forbidden.
    """
    tree = _parse_store()
    violations: list[str] = []

    for value, lineno in _all_string_constants(tree):
        if _CONN_STRING_WITH_CREDS_RE.search(value):
            violations.append(
                f"  line {lineno}: string literal contains embedded credentials: "
                f"{value!r}"
            )

    assert violations == [], (
        "store.py contains string literals that look like connection strings "
        "with embedded credentials — AC#5 requires credentials to come from "
        "the environment, not be hardcoded:\n" + "\n".join(violations)
    )


def test_no_credential_variable_assigned_string_literal():
    """No variable whose name signals a credential is assigned a string literal.

    AC#5: credentials appear nowhere in the repository.  An assignment such as
    ``password = "s3cr3t"`` or ``database_url = "postgresql://..."`` in any
    scope would bypass the environment-variable requirement.
    """
    tree = _parse_store()
    violations: list[str] = []

    for names, value, lineno in _all_assignments(tree):
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            literal_value = value.value
            if not literal_value:
                # Empty string is not a credential
                continue
            for name in names:
                if name.lower() in _CREDENTIAL_VAR_NAMES:
                    violations.append(
                        f"  line {lineno}: '{name}' is assigned a non-empty "
                        f"string literal — looks like a hardcoded credential"
                    )

    assert violations == [], (
        "store.py assigns string literals to credential-named variables — "
        "AC#5 requires credentials to come from the environment:\n"
        + "\n".join(violations)
    )


def test_database_url_function_reads_from_os_environ():
    """_database_url() must read from os.environ, not return a hardcoded string.

    AC#5: credentials are read from the environment at runtime.  The function
    must call os.environ.get or os.environ[] rather than returning a literal.
    """
    tree = _parse_store()
    func_nodes = _function_body_nodes(tree, "_database_url")

    assert func_nodes, (
        "_database_url function not found in store.py; cannot verify AC#5"
    )

    # Look for os.environ attribute access inside the function
    found_environ_access = False
    for node in func_nodes:
        if isinstance(node, ast.Attribute):
            if (
                node.attr == "environ"
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                found_environ_access = True
                break

    assert found_environ_access, (
        "_database_url() does not access os.environ — AC#5 requires the URL "
        "to be read from the environment, not hardcoded"
    )


def test_database_url_function_contains_no_hardcoded_url_literal():
    """_database_url() must not contain a string literal that looks like a URL.

    AC#5: no credentials in the code.  If _database_url() itself contains a
    hardcoded fallback like 'postgresql://localhost/myfriends' it still violates
    the requirement even if that fallback has no password embedded.
    """
    tree = _parse_store()
    func_nodes = _function_body_nodes(tree, "_database_url")

    assert func_nodes, (
        "_database_url function not found in store.py; cannot verify AC#5"
    )

    violations: list[str] = []
    url_pattern = re.compile(r"(?:postgres(?:ql)?|mysql|sqlite)://", re.IGNORECASE)

    for node in func_nodes:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if url_pattern.search(node.value):
                violations.append(
                    f"  line {node.lineno}: hardcoded URL literal in "
                    f"_database_url(): {node.value!r}"
                )

    assert violations == [], (
        "_database_url() contains hardcoded URL literals — "
        "AC#5 requires the URL to come from the environment:\n"
        + "\n".join(violations)
    )
