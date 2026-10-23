"""Guards against documentation drifting from the code (tables are generated; prose claims are checked here)."""
import dataclasses
import re
from pathlib import Path

import pytest

from core.detection.config import DetectionConfig
from core.detection.rules import RULE_DESCRIPTIONS

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
DETECTION = (ROOT / "docs" / "detection.md").read_text(encoding="utf-8")
ARCH = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")


def test_detection_doc_lists_every_rule_with_its_current_weight():
    d = DetectionConfig()
    for code, w in d.rule_weights.items():
        assert f"| `{code}` | {w:.2f} |" in DETECTION, code
    assert set(d.rule_weights) == set(RULE_DESCRIPTIONS)


def test_detection_doc_documents_every_config_field_with_its_default():
    d = DetectionConfig()
    for f in dataclasses.fields(d):
        if f.name == "rule_weights":
            continue
        assert f"| `{f.name}` | `{getattr(d, f.name)!r}` |" in DETECTION, f.name


def test_readme_route_table_matches_the_openapi_schema_exactly():
    from api.main import app
    spec = {(m.upper(), p) for p, v in app.openapi()["paths"].items() for m in v}
    block = README.split("<!-- routes:start -->")[1].split("<!-- routes:end -->")[0]
    documented = {(m, p) for m, p in re.findall(r"^\| (GET|POST|PATCH|PUT|DELETE) \| `([^`]+)` \|", block, flags=re.M)}
    assert documented == spec
    assert f"{len(spec)} operations" in block


def test_graph_feature_flag_is_documented_as_off_by_default_without_improvement_claims():
    assert DetectionConfig().include_graph_features_in_model is False
    for doc in (README, DETECTION):
        assert "include_graph_features_in_model" in doc
        assert "no demonstrated" in doc.lower()
    assert "`include_graph_features_in_model` | `False`" in DETECTION


@pytest.mark.parametrize("doc", [README, DETECTION, ARCH], ids=["README", "detection.md", "architecture.md"])
def test_docs_make_no_overstated_claims(doc):
    low = doc.lower()
    for phrase in ("improves detection", "improved detection", "improves model performance", "improves auc",
                   "calibrated probability of fraud", "proves fraud", "validated accuracy"):
        assert phrase not in low, phrase


def test_docs_carry_the_required_caveats():
    for doc in (README, DETECTION):
        low = doc.lower()
        assert "uncalibrated" in low and "not a probability" in low
        assert "synthetic" in low
    assert "leads for human review" in README.lower()


def test_readme_is_not_stale():
    for stale in ("Phase 0/1 complete", "Not implemented yet", "cd fraud-detection"):
        assert stale not in README, stale
    assert "Node.js ≥ 22.12" in README  # Vitest 5 requires it; Node 20 would break `npm test`


def test_model_only_severity_statement_is_accurate():
    assert "low severity by construction" not in DETECTION.lower() and "always low" not in DETECTION.lower()
    assert "exactly 100" in DETECTION
