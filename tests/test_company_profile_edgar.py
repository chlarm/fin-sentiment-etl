"""Tests for the Item 1 "Business" extraction from 10-K documents.

The cases here are the ones that actually went wrong on real filings, plus
the two structural failures that cannot be fixed by parsing.
"""
from src.extract.company_profile_edgar import (
    MAX_BUSINESS_CHARS,
    MIN_BUSINESS_CHARS,
    _html_to_text,
    extract_business_section,
)


def _body(n_chars: int, filler: str = "The Company designs and sells products. ") -> str:
    return filler * (n_chars // len(filler) + 1)


def test_extracts_the_body_section():
    text = "Cover page. Item 1. Business " + _body(6_000) + " Item 1A. Risk Factors and so on."
    section = extract_business_section(text)
    assert section is not None
    assert section.startswith("Item 1. Business")
    assert "Risk Factors" not in section


def test_table_of_contents_start_does_not_swallow_the_document():
    """A TOC line names both items before either section begins.

    Pairing every start with every end let the TOC "Item 1. Business" pair
    with the LAST risk-factors mention, producing a 214,000-character
    "business description" for Coca-Cola. Each start must pair with the first
    end that follows it.
    """
    text = (
        "TABLE OF CONTENTS Item 1. Business 3 Item 1A. Risk Factors 12 "
        + "Item 1. Business " + _body(8_000)
        + " Item 1A. Risk Factors " + _body(40_000)
        + " Item 1A. Risk Factors continued"
    )
    section = extract_business_section(text)
    assert section is not None
    assert len(section) < 20_000
    assert "TABLE OF CONTENTS" not in section


def test_returns_none_when_no_item_1_heading_exists():
    """MSFT and INTC: the heading is genuinely absent from the body.

    INTC uses a cross-reference index mapping items to page numbers; MSFT
    heads the section differently. Returning a fragment that looks like a
    business description would be worse than returning nothing.
    """
    text = "Form 10-K Cross-Reference Index. Business ... 4. Risk Factors ... 20. " + _body(9_000)
    assert extract_business_section(text) is None


def test_returns_none_when_risk_factors_never_follows():
    text = "Item 1. Business " + _body(9_000)
    assert extract_business_section(text) is None


def test_rejects_a_section_that_is_too_short_to_be_the_real_one():
    text = "Item 1. Business see page 4. Item 1A. Risk Factors see page 20."
    assert extract_business_section(text) is None
    assert MIN_BUSINESS_CHARS > 100


def test_rejects_a_section_that_swallowed_the_document():
    text = "Item 1. Business " + _body(MAX_BUSINESS_CHARS + 10_000) + " Item 1A. Risk Factors"
    assert extract_business_section(text) is None


def test_heading_variants_are_matched():
    for heading, end in [
        ("Item 1. Business", "Item 1A. Risk Factors"),
        ("ITEM 1 BUSINESS", "ITEM 1A RISK FACTORS"),
        ("Item 1 — Business", "Item 1A — Risk Factors"),
        ("Item  1.  Business", "Item  1A.  Risk  Factors"),
    ]:
        text = f"{heading} " + _body(6_000) + f" {end} rest"
        assert extract_business_section(text) is not None, heading


def test_html_to_text_drops_scripts_and_entities():
    raw = (
        "<html><head><style>.a{color:red}</style><script>var x = 1;</script></head>"
        "<body><p>Apple&nbsp;Inc. designs &amp; sells\n\n  devices.</p></body></html>"
    )
    text = _html_to_text(raw)
    assert "color:red" not in text
    assert "var x" not in text
    assert "Apple Inc. designs & sells devices." in text
