"""OrchestratorAgent — deterministic runtime plus bounded Strands tools."""
from __future__ import annotations

import json

from .. import db
from ..models import Category, Geo, GeoSource, TenantConfig
from ..pipeline import PipelineResult, Submission, run

SYSTEM_PROMPT = """You are the WardWatch orchestrator. Investigate with tools before
taking action: analyze the issue, inspect nearby duplicates, find the configured
authority, and assess priority. Create an internal record only when location and a
description are present. External authority submission always requires separate human
approval and is unavailable through this agent. Ask exactly one question if intake or
location is ambiguous. Never invent an authority response, ticket, or resolution."""


def handle_submission(sub: Submission, config: TenantConfig | None = None) -> PipelineResult:
    """Deterministic lifecycle driver used by the webhook route."""
    return run(sub, config)


def build_agent():
    """Build the interactive/AgentCore Strands agent."""
    from strands import Agent, tool

    from ..config import get_settings
    from ..priority import assess
    from .dedup import find_duplicate
    from .intake import analyze
    from .routing import route

    @tool
    def analyze_issue(transcript: str) -> str:
        """Classify a citizen description and calculate transparent priority."""
        intake = analyze(None, transcript)
        priority = assess(intake.category, intake.severity, intake.description)
        return json.dumps({
            **intake.model_dump(mode="json"),
            "priority": priority.priority.value,
            "priority_score": priority.score,
            "priority_factors": priority.factors,
        })

    @tool
    def search_existing_reports(
        tenant_id: str,
        ward_id: str,
        category: str,
        lat: float,
        lng: float,
        geo_source: str = "whatsapp_share",
    ) -> str:
        """Check for a nearby open report with deterministic deduplication rules."""
        decision = find_duplicate(
            Geo(lat=lat, lng=lng, source=GeoSource(geo_source)),
            db.open_complaints_by_category(tenant_id, ward_id, Category(category).value),
        )
        return json.dumps({
            "duplicate": decision.is_duplicate,
            "complaint_id": decision.match.complaint_id if decision.match else None,
            "distance_m": decision.distance_m,
            "needs_human_review": decision.needs_review,
        })

    @tool
    def find_authority(tenant_id: str, category: str, description: str = "") -> str:
        """Resolve the department from the tenant's configured authority directory."""
        return route(
            Category(category), description, db.get_tenant_config(tenant_id)
        ).value

    @tool
    def process_submission(
        tenant_id: str,
        ward_id: str,
        citizen_phone: str,
        transcript: str,
        lat: float,
        lng: float,
    ) -> str:
        """Create or merge an internal record; this never submits externally."""
        res = run(
            Submission(
                tenant_id=tenant_id,
                ward_id=ward_id,
                citizen_phone=citizen_phone,
                photo=None,
                transcript=transcript,
                shared_location=(lat, lng),
            )
        )
        return res.message

    from strands.models import BedrockModel

    s = get_settings()
    return Agent(
        model=BedrockModel(
            model_id=s.bedrock_reasoning_model_id, region_name=s.aws_region
        ),
        system_prompt=SYSTEM_PROMPT,
        tools=[analyze_issue, search_existing_reports, find_authority, process_submission],
    )
