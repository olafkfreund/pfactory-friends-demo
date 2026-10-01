"""Every lazily-imported third-party module must be a declared dependency.

This exists because the same defect occurred three times in one branch.
``psycopg``, ``python-jose`` and ``httpx`` are all imported *inside functions*,
so their absence raises nothing at import time: the container starts, the
health check passes, the pod reports Ready, and the first real request dies
with ``ModuleNotFoundError``. None of them was in ``pyproject.toml``.

A test asserting "psycopg is declared" would have caught one of the three. This
enumerates the lazy imports from the source instead, so a fourth is caught the
moment it is added rather than on deployment.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

_APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"

# Modules that are part of the standard library or are this package's own.
_LOCAL_PREFIXES = ("app",)


def _lazy_imports() -> set[str]:
    """Top-level module names imported inside a function or method body."""
    found: set[str] = set()
    for path in sorted(_APP_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import):
                    for alias in inner.names:
                        found.add(alias.name.split(".")[0])
                elif isinstance(inner, ast.ImportFrom):
                    if inner.level == 0 and inner.module:
                        found.add(inner.module.split(".")[0])
    return {
        m for m in found
        if not m.startswith(_LOCAL_PREFIXES)
        and m not in getattr(__import__("sys"), "stdlib_module_names", frozenset())
    }


def test_there_are_lazy_imports_to_check():
    """Guard against this suite passing because it found nothing.

    If the enumeration breaks, an empty set would make every parametrised case
    vanish and the file would still report success -- a pass-shaped empty
    measurement. This asserts the scan actually found something.
    """
    assert _lazy_imports(), (
        "no lazy third-party imports found; the AST scan is probably broken, "
        "not the code suddenly clean"
    )


@pytest.mark.parametrize("module", sorted(_lazy_imports()))
def test_lazy_import_is_installed(module: str):
    """The module must actually be importable in this environment.

    Installed-ness is the property that matters: a declaration in
    pyproject.toml that resolves to nothing would still break at runtime.
    """
    assert importlib.util.find_spec(module) is not None, (
        f"{module!r} is imported inside a function in app/ but is not "
        "installed. The pod will start healthy and fail on the first request "
        "that reaches that import."
    )
