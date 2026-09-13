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


def test_unclear_evidence_requests_a_clearer_photo(fakes):
    from wardwatch.agents.orchestrator import handle_submission
    from wardwatch.llm import set_vision_hook
    from wardwatch.pipeline import Submission

    set_vision_hook(lambda **kw: {
        "category": "pothole",
        "severity": "medium",
        "description": "Reported pothole is not visible.",
        "needs_clarification": False,
        "evidence_relevant": False,
        "evidence_note": "Please upload a clearer road photo.",
    })
    result = handle_submission(Submission(
        tenant_id="MDU-CORP", ward_id="MDU-W14", citizen_phone="1",
        photo=b"unclear", transcript="pothole", shared_location=(9.9252, 78.1198),
    ))
    assert result.kind == "needs_clarification"
    assert "clearer" in result.message
