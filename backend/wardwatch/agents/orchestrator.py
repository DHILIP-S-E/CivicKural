"""OrchestratorAgent — owns the complaint lifecycle, calls the others as tools (spec §3).

The heavy reasoning model is optional here: `handle_submission` runs the
deterministic pipeline directly, while `build_agent` exposes the same steps as
Strands tools for the demo's "agent decides" narrative.
"""
from __future__ import annotations

from ..models import TenantConfig
from ..pipeline import PipelineResult, Submission, run

SYSTEM_PROMPT = """You are the WardWatch orchestrator. For each citizen submission you:
1. call pin_location, 2. call run_intake, 3. call check_duplicate,
4. call route_complaint, 5. call persist_complaint.
Stop and ask the citizen exactly one question if intake or location is ambiguous.
Never ask about more than one thing at a time."""


def handle_submission(sub: Submission, config: TenantConfig | None = None) -> PipelineResult:
    """Deterministic lifecycle driver used by the webhook route."""
    return run(sub, config)


def build_agent():
    """Strands Agent wrapping the pipeline as a single tool (demo/reasoning path)."""
    from strands import Agent, tool

    from ..config import get_settings
    from ..llm import _strands_agent  # noqa: F401 - reuse model config

    @tool
    def process_submission(
        tenant_id: str,
        ward_id: str,
        citizen_phone: str,
        transcript: str,
    ) -> str:
        """Process a text-only civic complaint submission end to end."""
        res = run(
            Submission(
                tenant_id=tenant_id,
                ward_id=ward_id,
                citizen_phone=citizen_phone,
                photo=None,
                transcript=transcript,
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
        tools=[process_submission],
    )
