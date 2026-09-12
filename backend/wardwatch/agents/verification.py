"""VerificationAgent — before/after photo compare (spec §8).

Inconclusive or negative -> pending_verification, never auto-resolved.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..llm import vision_json
from ..models import Category, Status

SYSTEM_PROMPT = """You verify municipal repair work. You are given a BEFORE photo and
an AFTER photo of a reported {category} issue. Return ONLY JSON:
  resolved: boolean   - true only if the AFTER photo clearly shows the issue fixed
  confidence: low | medium | high
  reason: one short sentence
Be conservative: if you cannot clearly see the fix, resolved must be false.
"""


@dataclass
class VerificationOutcome:
    status: Status
    confidence: str
    reason: str


def verify(category: Category, before: bytes, after: bytes) -> VerificationOutcome:
    data = vision_json(
        SYSTEM_PROMPT.format(category=category.value),
        "First image is BEFORE, second image is AFTER.",
        [before, after],
    )
    resolved = bool(data.get("resolved")) and data.get("confidence") in {"medium", "high"}
    return VerificationOutcome(
        status=Status.RESOLVED if resolved else Status.PENDING_VERIFICATION,
        confidence=str(data.get("confidence", "low")),
        reason=str(data.get("reason", "")),
    )
