"""Replaceable civic-authority adapter used by the hackathon prototype.

This module is deliberately labelled simulated.  A real municipal API can
implement the same interface later without changing the complaint lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .models import Complaint


@dataclass(frozen=True)
class SubmissionReceipt:
    ticket_id: str
    provider: str = "simulated_civic_authority"
    simulated: bool = True


def submit(complaint: Complaint) -> SubmissionReceipt:
    suffix = hashlib.sha256(
        f"{complaint.tenant_id}:{complaint.complaint_id}".encode("utf-8")
    ).hexdigest()[:8].upper()
    return SubmissionReceipt(ticket_id=f"SIM-{suffix}")
