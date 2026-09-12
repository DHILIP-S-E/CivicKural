from wardwatch.agents.intake import analyze
from wardwatch.llm import set_vision_hook
from wardwatch.models import Category, Severity


def test_analyze_detects_tamil_language(fakes):
    set_vision_hook(
        lambda **kw: {
            "category": "pothole",
            "severity": "high",
            "description": "பேருந்து நிலையத்திற்கு அருகில் பெரிய பள்ளம் உள்ளது",
            "language": "ta",
            "needs_clarification": False,
            "clarification_question": None,
        }
    )
    result = analyze(None, "பேருந்து நிலையத்திற்கு அருகில் ஒரு பெரிய பள்ளம் உள்ளது")
    assert result.language == "ta"
    assert result.category == Category.POTHOLE
    assert result.severity == Severity.HIGH
    assert "பள்ளம்" in result.description


def test_analyze_defaults_language_to_en_when_missing(fakes):
    set_vision_hook(
        lambda **kw: {
            "category": "garbage",
            "severity": "low",
            "description": "Garbage not collected on the street.",
            "needs_clarification": False,
            "clarification_question": None,
        }
    )
    result = analyze(None, "garbage not collected")
    assert result.language == "en"
