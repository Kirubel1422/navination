import copy

import pytest

from app.knowledge.seed_loader import SeedBundle, load_seed, validate_bundle


@pytest.fixture(scope="module")
def bundle() -> SeedBundle:
    return load_seed()


def problems_after(bundle: SeedBundle, mutate) -> list[str]:  # type: ignore[no-untyped-def]
    data = copy.deepcopy(bundle.model_dump(by_alias=True))
    mutate(data)
    return validate_bundle(SeedBundle.model_validate(data))


def test_seed_is_valid(bundle):
    assert validate_bundle(bundle) == []
    assert 8 <= len(bundle.services) <= 12


def test_detects_duplicate_ids(bundle):
    problems = problems_after(
        bundle, lambda d: d["services"].append(copy.deepcopy(d["services"][0]))
    )
    assert any("duplicate service id" in p for p in problems)


def test_detects_missing_references(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        d["dependencies"][0]["to"] = "ghost-service"
        d["services"][0]["requirements"][0]["source_ids"] = ["src-ghost"]

    problems = problems_after(bundle, mutate)
    assert any("unknown service ghost-service" in p for p in problems)
    assert any("src-ghost" in p for p in problems)


def test_detects_invalid_links(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        d["services"][0]["official_url"] = "http://uaepass.ae/"
        d["services"][1]["support_url"] = "https://evil.example/"

    problems = problems_after(bundle, mutate)
    assert any("absolute HTTPS" in p for p in problems)
    assert any("evil.example" in p for p in problems)


def test_detects_missing_evidence(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        d["services"][1]["requirements"][0]["source_ids"] = []

    assert any("missing evidence" in p for p in problems_after(bundle, mutate))


def test_detects_required_cycles(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        d["dependencies"].append(
            {
                "id": "dep-cycle",
                "from": "mofa-attestation-abroad",
                "to": "uae-pass-account",
                "kind": "required",
                "explanation": {"en": "x", "ar": "x"},
                "source_ids": ["src-mofa-attestation"],
                "condition": None,
            }
        )

    assert any("cycle" in p for p in problems_after(bundle, mutate))


def test_detects_unsupported_mandatory_edges(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        dep = next(x for x in d["dependencies"] if x["id"] == "dep-partner-mohesr")
        dep["kind"] = "required"

    assert any("unsupported mandatory edge" in p for p in problems_after(bundle, mutate))


def test_detects_missing_translations(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        d["services"][0]["title"]["ar"] = ""

    with pytest.raises(Exception, match="at least 1 character"):
        problems_after(bundle, mutate)


def test_detects_invalid_rule_values(bundle):
    def mutate(d):  # type: ignore[no-untyped-def]
        d["services"][1]["requirements"][0]["rule"] = {
            "field": "residency_status",
            "in": ["tourist"],
        }

    assert any("not valid for residency_status" in p for p in problems_after(bundle, mutate))
