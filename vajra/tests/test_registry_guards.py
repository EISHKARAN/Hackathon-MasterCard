"""Feature-registry guards: no protected attributes, audit fields excluded, view masking is real."""
from __future__ import annotations
import re
import pytest
from features.registry import load_registry, VIEWS


_PROTECTED = re.compile(r"\b(age_of_customer|gender|sex|religion|caste|income|ethnic|race|marital)\b", re.I)


def test_no_protected_attributes():
    """No feature encodes a protected attribute. entity_age is TRANSACTION-entity age, not customer age."""
    reg = load_registry()
    offenders = [n for n in reg.names if _PROTECTED.search(n)]
    assert not offenders, f"features look like protected attributes: {offenders}"


def test_audit_fields_excluded_from_model_matrix():
    """label_channel_disagreement is computed and audited but must NOT be a model column."""
    reg = load_registry()
    model = set(reg.model_feature_names())
    for a in reg.audit_only_names:
        assert a not in model, f"audit-only field {a} leaked into the model matrix"


def test_propensity_is_never_a_feature():
    """incumbent_accept_probability is the PROPENSITY; feeding it to the model is a leak."""
    reg = load_registry()
    assert "incumbent_accept_probability" not in reg.names


def test_view_masking_removes_features():
    """An acquirer cannot construct PAN-canonical aggregation; those features are ABSENT, not zeroed."""
    reg = load_registry()
    issuer = set(reg.features_for_view("issuer"))
    acquirer = set(reg.features_for_view("acquirer"))
    # The acquirer holds no token-to-PAN map, so PAN-canonical velocity is absent for it.
    assert any("pan_canonical" in f for f in issuer)
    assert not any("pan_canonical" in f for f in acquirer), "acquirer should not have PAN-canonical features"
    assert len(acquirer) < len(issuer)


def test_every_family_names_an_attack():
    """A feature family with no `catches` mechanism is decoration — the loader must reject it."""
    reg = load_registry()  # loads without error means every family named a mechanism
    for f in reg.features:
        assert f.catches, f"feature {f.name} has no attack mechanism"
