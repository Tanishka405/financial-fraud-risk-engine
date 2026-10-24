"""Enforces the dependency claims made in the docs, using an AST scan (catches function-level imports too)."""
import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STD = set(sys.stdlib_module_names)
DIST = {"yaml": "pyyaml", "dateutil": "python-dateutil", "sklearn": "scikit-learn", "multipart": "python-multipart"}
FORBIDDEN_IN_CORE = {"fastapi", "starlette", "uvicorn", "pydantic", "sqlalchemy", "psycopg", "psycopg2", "sqlite3", "flask", "django", "api"}


def third_party_imports(pkg: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in sorted((ROOT / pkg).rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            for m in mods:
                top = m.split(".")[0]
                if top not in STD and top not in ("core", "api"):
                    out.setdefault(top, []).append(f"{f.relative_to(ROOT)}:{node.lineno}")
    return out


def declared():
    py = tomllib.loads((ROOT / "pyproject.toml").read_text())
    norm = lambda specs: {re.split(r"[<>=!~\[ ;]", s)[0].lower() for s in specs}  # noqa: E731
    runtime = norm(py["project"]["dependencies"])
    extras = {k: norm(v) for k, v in py["project"]["optional-dependencies"].items()}
    return runtime, extras


def test_every_core_import_is_a_declared_runtime_dependency():
    runtime, _ = declared()
    missing = {m: w for m, w in third_party_imports("core").items() if DIST.get(m, m).lower() not in runtime}
    assert not missing, f"core imports undeclared packages: {missing}"


def test_every_api_import_is_declared_in_runtime_or_the_api_and_dev_extras():
    runtime, extras = declared()
    for m, where in third_party_imports("api").items():
        d = DIST.get(m, m).lower()
        assert d in runtime or (d in extras["api"] and d in extras["dev"]), f"{m} imported at {where[:2]} but not declared"


def test_core_has_no_web_or_database_dependency():
    core = third_party_imports("core")
    stdlib_db = {n.split(".")[0] for f in (ROOT / "core").rglob("*.py") for n in
                 [a.name for x in ast.walk(ast.parse(f.read_text())) if isinstance(x, ast.Import) for a in x.names]
                 + [x.module for x in ast.walk(ast.parse(f.read_text())) if isinstance(x, ast.ImportFrom) and x.module and x.level == 0]}
    assert not (set(core) | stdlib_db) & FORBIDDEN_IN_CORE, sorted((set(core) | stdlib_db) & FORBIDDEN_IN_CORE)


def test_design_doc_dependency_sentence_matches_the_actual_core_imports():
    doc = (ROOT / "docs" / "design_decisions.md").read_text(encoding="utf-8")
    sentence = doc.split("`core/` imports only", 1)[1].split("This means", 1)[0].lower()
    for m in third_party_imports("core"):
        assert DIST.get(m, m).lower() in sentence, f"design_decisions.md does not mention core's dependency {m}"
    assert "`db/` will convert" not in doc  # the unbuilt plan must not read as current
