"""IntakeAgent — Bedrock Claude vision + transcript -> structured JSON (spec §2)."""
from __future__ import annotations

from ..llm import vision_json
from ..models import Category, IntakeResult, Severity

SYSTEM_PROMPT = """You are the intake analyst for a municipal complaint system.
Given a photo of a civic issue and a transcript of the citizen's voice note, return
ONLY a JSON object with keys:
  category: one of pothole | garbage | water_leak | streetlight | other
  severity: one of low | medium | high  (infer from language like "blocking traffic")
  description: a single factual sentence, no more than 20 words, written in the
    citizen's ORIGINAL language (do not translate it to English)
  language: the ISO 639-1 code of the language the citizen's transcript is written
    in (e.g. "ta" for Tamil, "en" for English, "hi" for Hindi). Detect this from the
    transcript itself.
  needs_clarification: boolean - true ONLY if the category is genuinely ambiguous
  clarification_question: a single short question, or null
The category and severity values themselves must always be the fixed English enum
values above, regardless of what language the citizen wrote in.
Do not include any prose outside the JSON object.
"""


def analyze(photo: bytes | None, transcript: str) -> IntakeResult:
    images = [photo] if photo else []
    data = vision_json(SYSTEM_PROMPT, f"Voice note transcript: {transcript}", images)
    return IntakeResult(
        category=Category(data["category"]),
        severity=Severity(data.get("severity", "medium")),
        description=data["description"].strip(),
        language=data.get("language") or "en",
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarification_question=data.get("clarification_question"),
    )
