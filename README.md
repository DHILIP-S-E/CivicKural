# WardWatch

Multi-agent civic complaint intake, deduplication, routing, SLA tracking and
automatic escalation. A citizen's WhatsApp photo + voice note becomes a
deduplicated, routed, SLA-tracked complaint — and it escalates on its own when
nobody acts.

Built for the AWS "Agents for Humans" hackathon (Good Neighbor Agents track),
on the **Strands Agents SDK** + Amazon Bedrock.

## Architecture

```
WhatsApp webhook ──► OrchestratorAgent
                        │  pipeline.py (deterministic glue)
                        ├─ pin_location   4-tier: whatsapp_share ▸ exif ▸ geocoded ▸ described
                        ├─ IntakeAgent    Bedrock Claude vision+text ▸ {category, severity, description}
                        ├─ DedupAgent     pure fn — geo-source-adjusted radius
                        ├─ RoutingAgent   rule table (+ rare LLM for `other`)
                        └─ persist        DynamoDB + S3
EventBridge 6h  ──► EscalationAgent  pure fn — tiered breach notifications
EventBridge 7d  ──► PatternAgent     clustering + 1 summary call ▸ infrastructure_risk_flag
officer upload  ──► VerificationAgent Bedrock Claude vision — before/after compare
```

Only 3 of 7 components call a model: `IntakeAgent`, `VerificationAgent`,
`PatternAgent` (and `RoutingAgent` only for ambiguous `other`).

| Path | Purpose |
|---|---|
| `backend/wardwatch/agents/` | the seven agents |
| `backend/wardwatch/pipeline.py` | location pinning + intake→dedup→routing→persist |
| `backend/wardwatch/api/` | FastAPI: webhook, officer, admin, public routes |
| `backend/wardwatch/schedulers/` | Lambda handlers for the two EventBridge sweeps |
| `infra/template.yaml` | AWS SAM — DynamoDB, S3, EventBridge, sweep Lambdas |
| `frontend/` | Next.js officer + public dashboards |

Data model and business rules are in the spec; the authoritative copy of the
rules lives in `sla.py`, `geo.py`, `agents/escalation.py`, `agents/pattern.py`.

## Local development

```bash
# 1. Backend deps
python -m pip install -e ".[dev]"

# 2. Run the tests (moto mocks DynamoDB + S3; Bedrock/WhatsApp are faked)
python -m pytest -q

# 3. Configure AWS for a live run
cp .env.example .env          # set AWS_REGION, table, bucket, model IDs
#   Bedrock, DynamoDB, S3 are used for real; WHATSAPP_TOKEN empty => FakeWhatsApp

# 4. Create the cloud resources
sam build -t infra/template.yaml && sam deploy --guided

# 5. Serve the API
uvicorn wardwatch.api.app:app --reload --app-dir backend

# 6. Seed sample data + mint tokens
python -m wardwatch.devtools seed
python -m wardwatch.devtools token officer MDU-W14
python -m wardwatch.devtools token admin MDU-W14

# 7. Frontend
cd frontend && npm install && cp .env.local.example .env.local && npm run dev
#   open http://localhost:3000 , paste the officer token at /login
```

## Simulating a citizen submission

```bash
curl -X POST localhost:8000/webhook/whatsapp -H 'content-type: application/json' -d '{
  "from_phone": "+91 90000 11111",
  "ward_id": "MDU-W14",
  "transcript": "huge pothole near the bus stand, blocking traffic",
  "location": [9.9252, 78.1198]
}'
```

Send a second call within 75 m with the same category → response `kind: "merged"`,
`"already tracked as #WM-…"`.

## Demo script

1. `curl` the webhook → complaint appears in the officer queue at `/`.
2. Open it, **Mark in progress** (SLA clock keeps running).
3. Back-date its `sla_deadline` (or wait), invoke `EscalationSweepFn` →
   `escalation_tier` bumps, dept contact is notified, `/escalations` shows it.
4. Upload an "after" photo on the detail page → `VerificationAgent` decides:
   confirmed → `resolved`; inconclusive → `pending_verification` (stays in the sweep).
5. `/public` shows department SLA % and binned hotspot density — no PII.

## Verification

- **Unit + integration:** `python -m pytest -q` — 31 tests covering the geo radius
  table, SLA deadlines, dedup match/review, routing, escalation tiers, the
  3-in-90-days/150 m pattern threshold, the end-to-end pipeline (create → merge →
  escalate → verify), public-endpoint PII assertions, and backend role
  enforcement (officer token → `/admin/settings` returns 403).
- **Cloud smoke:** after `sam deploy`, `curl` the webhook, confirm the item in the
  DynamoDB console and the object in S3, then invoke both sweep Lambdas from the
  console.

## Known build notes

- WhatsApp compression sometimes strips photo EXIF GPS — tier 2 of location
  pinning may silently fall through to geocoding; test with a real forwarded image.
- `geo.WARD_BBOX` and `wards.TENANT_WARDS` are static here; a real deployment
  stores ward geometry and rosters in DynamoDB.
- The real WhatsApp webhook payload is normalised to `WhatsAppInbound` by the
  messaging-provider integration, which is out of scope for this scaffold.
