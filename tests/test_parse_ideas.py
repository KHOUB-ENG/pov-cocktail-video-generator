"""
Tests for the idea-parsing logic in the orchestrator.

`parse_ideas_from_response` is the pure, deterministic heart of the pipeline's
first stage: it turns free-form Gemini text into a structured list of idea
dicts using five fallback strategies. These tests pin that behaviour so the
parser can be refactored safely.
"""

import main


def test_title_anchor_strategy_parses_each_block():
    """Strategy 0: `TITLE:` line anchors — the primary/current prompt format."""
    text = (
        "TITLE: The Clarified Milk Punch\n"
        "COCKTAIL: Milk Punch\n\n"
        "TITLE: One Lemon, Measured\n"
        "COCKTAIL: Whiskey Sour\n\n"
        "TITLE: The Drill Martini\n"
        "COCKTAIL: Martini\n"
    )
    ideas = main.parse_ideas_from_response(text)
    assert len(ideas) == 3
    assert ideas[0]["title"] == "The Clarified Milk Punch"
    assert ideas[0]["cocktail"] == "Milk Punch"
    assert ideas[2]["title"] == "The Drill Martini"
    assert ideas[2]["cocktail"] == "Martini"


def test_title_anchor_is_case_and_bold_insensitive():
    text = (
        "**Title:** First Idea\n**Cocktail:** Negroni\n\n"
        "**Title:** Second Idea\n**Cocktail:** Daiquiri\n"
    )
    ideas = main.parse_ideas_from_response(text)
    assert len(ideas) == 2
    assert ideas[0]["title"] == "First Idea"
    assert ideas[1]["cocktail"] == "Daiquiri"


def test_horizontal_rule_strategy():
    """Strategy 1: `---` separators when there are no TITLE anchors.

    Requires 2+ rules (3 blocks) — a single rule does not trigger this path.
    """
    text = (
        "The Sazerac Problem\nAn old recipe, re-measured.\n"
        "\n---\n"
        "The Gimlet Ratio\nLime, sugar, and a verdict.\n"
        "\n---\n"
        "The Daiquiri Standard\nThree ingredients, one answer.\n"
    )
    ideas = main.parse_ideas_from_response(text)
    assert len(ideas) == 3
    # First non-empty line becomes the title when no explicit TITLE: field.
    assert ideas[0]["title"] == "The Sazerac Problem"
    assert ideas[2]["title"] == "The Daiquiri Standard"


def test_never_returns_more_than_nine():
    """MAX_IDEAS cap holds even when the model returns more blocks."""
    text = "".join(f"TITLE: Idea {i}\nCOCKTAIL: Drink {i}\n\n" for i in range(1, 13))
    ideas = main.parse_ideas_from_response(text)
    assert len(ideas) == 9


def test_idea_text_preserves_full_block():
    text = "TITLE: A\nCOCKTAIL: B\n\nTITLE: C\nCOCKTAIL: D\n"
    ideas = main.parse_ideas_from_response(text)
    assert "TITLE: A" in ideas[0]["idea_text"]
    assert "COCKTAIL: B" in ideas[0]["idea_text"]


def test_extract_fields_falls_back_to_first_line_as_title():
    fields = main._extract_idea_fields("Just a bare headline\nsome body text")
    assert fields["title"] == "Just a bare headline"
    assert fields["cocktail"] == ""
