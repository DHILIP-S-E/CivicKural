# WardWatch / CivicFix requirements audit

Audit date: 2026-09-13 (updated same day with productionization pass results)

The WardWatch specification is treated as the binding privacy and lifecycle
contract.  The broader CivicFix document is treated as an extension roadmap.
Where they conflict, WardWatch privacy wins: public accountability remains
aggregate-only, while a citizen can access only their own report with an opaque
token.

## Implemented and verified

| Requirement | Evidence |
|---|---|
| Text, English/Tamil voice, photo, video and consent-based GPS intake | `routes_webhook.py`, `routes_public.py`, `transcribe.py`, `/report` |
| Multi-message WhatsApp conversation assembly | expiring DynamoDB `InboundSession`; photo/voice/location events are combined without storing a raw phone number |
| WhatsApp webhook authenticity | optional Meta `X-Hub-Signature-256` verification using the app secret |
| Citizen-language responses | deterministic English/Tamil message catalogue plus model-detected intake language |
| Four-tier location fallback and ward-biased geocoding | `pipeline.pin_location`, `geocode.py`, `geo.py` |
| Bedrock structured multimodal classification | `agents/intake.py`, `llm.py` |
| Evidence relevance and unclear-photo handling | structured `evidence_relevant`/`evidence_note`; unclear evidence requests one clearer photo |
| Geo-confidence-aware deterministic deduplication | `agents/dedup.py`, `geo.py` |
| Deterministic routing with tenant overrides | `agents/routing.py`, `TenantConfig` |
| Transparent priority assessment | `priority.py`; stored `priority_factors` and score |
| DynamoDB/S3 source of truth and private evidence | `db.py`, `storage.py`, private S3 deployment |
| Category SLA clock and 6-hour escalation | `sla.py`, `agents/escalation.py`, EventBridge worker |
| Officer/supervisor notification routing and citizen update queue | `notify.py`, `schedulers/escalation_sweep.py` |
| Privacy-safe proactive citizen notification routing | KMS-encrypted destinations; only ciphertext is persisted and all reporters on a merged issue can be notified |
| Before/after AI verification gate | `agents/verification.py`; resolved timestamp and assessment are persisted |
| Citizen confirmation/rejection | token-protected citizen routes and `/issues` |
| Community support without public complaint disclosure | signed opaque community references; supporting evidence is stored |
| Weekly 90-day/150m pattern detection | `agents/pattern.py`; flags are now idempotent |
| Officer, coordinator and admin role/ward enforcement | coordinators are read-only; mutation and settings gates are backend-enforced |
| Aggregate-only public accountability | department SLA, tier-3 breaches, density map, totals and success metrics |
| Human approval for consequential authority action | officer approval endpoint and UI |
| Replaceable simulated authority API | `authority.py`; responses are explicitly labelled simulated |
| Strands tool-choosing orchestrator and AgentCore Runtime adapter | bounded investigation/action tools in `orchestrator.py`; `agentcore_main.py` implements the AgentCore entrypoint contract |
| Deployable API and scheduled workers | `infra/template.yaml`; Linux Lambda packages prepared |
| Deployable static Next.js frontend | static export configuration and query-based runtime detail routes |

Automated verification currently covers 61 backend tests (52 pre-existing + 9
added in this pass) plus a clean TypeScript check and successful production
static export.

## Productionization pass (this audit): fixed, added, and prepared

A scoped follow-up pass fixed concrete gaps found by re-auditing the codebase
against this document's own claims, without rebuilding features already
verified above. Changes made and verified locally (not yet deployed):

| Area | Change | Status |
|---|---|---|
| Security | `POST /webhook/simulate` was an unauthenticated production write endpoint bypassing WhatsApp entirely; now off by default (`ENABLE_SIMULATE_ENDPOINT`) and otherwise requires officer/admin auth | **Fixed, verified by test** |
| Auth | Raw HS256 JWT path issued tokens with no `exp` claim (never expired); tokens now expire after `jwt_expires_minutes` (default 12h) and expired tokens are rejected with 401 | **Fixed, verified by test** |
| Auth (frontend) | Cognito session in `lib/auth.ts` never proactively checked expiry or used the stored refresh token; now checks expiry before each API call and silently refreshes via `REFRESH_TOKEN_AUTH`, falling back to a `session_expired` redirect to `/login` | **Fixed, verified via `tsc`/build** |
| Frontend UX | No dedicated error boundary, 404, loading, or session-expired states | Added `app/error.tsx`, `app/not-found.tsx`, `app/loading.tsx`, and a session-expired notice on the login page | **Fixed, verified via `tsc`/build** |
| Notifications | Escalation-sweep citizen notifications silently swallowed failures with no retry, delivery record, or protection against double-send on re-run | Added a per-complaint notify log (`citizen_notify_log`), one bounded retry, and idempotency against a prior `SENT` entry for the same tier | **Fixed, verified by test** |
| Internal health | No internal system-health view existed | Added `GET /admin/health` (admin-gated: last escalation/pattern sweep run time, recent notification failure count) and an admin-only frontend page consuming it | **Fixed, verified by test + build** |
| IaC | `infra/cognito-user-pool.json` and `infra/runtime-additions-policy.json` were standalone CLI payloads, not represented in `infra/template.yaml`, even though the frontend already depends on the Cognito pool they describe | Folded into `template.yaml` as proper `AWS::Cognito::UserPool`/`UserPoolClient` resources plus the one missing IAM action | **Prepared only — not applied/deployed** |
| Secrets | `JWT_SECRET` is a plain `NoEcho` CFN parameter/Lambda env var, not Secrets Manager | Added a condition-gated `AWS::SecretsManager::Secret` resource and an `!If` switch in `template.yaml`, left disabled by default | **Prepared only — requires the same explicit rotation approval as the pending JWT secret rotation below, not applied** |

Nothing above was deployed to the live stack (`sam deploy`/`aws cloudformation`
were never run in this pass); `infra/template.yaml` changes are template-only
until reviewed and applied deliberately.

## AWS deployment status

- API: `https://66qnoftc0m.execute-api.ap-south-1.amazonaws.com` (live health
  and aggregate dashboard smoke tests pass).
- Frontend: `https://production.d3swendy0zube6.amplifyapp.com` (Amplify
  production deployment succeeds and returns HTTP 200).
- The API, escalation sweep and pattern sweep Lambda functions are active on the
  final code packages. DynamoDB TTL is enabled, and the scoped Amazon Location
  index and rotating KMS key are provisioned.
- The last security configuration step is intentionally pending explicit
  approval because rotating the exposed JWT signing secret invalidates all
  currently issued officer/admin tokens. The same configuration update attaches
  the KMS alias to the API and escalation worker and raises the API timeout from
  30 to 60 seconds.

## Partial or environment-dependent

| Requirement | Remaining dependency |
|---|---|
| Live WhatsApp sandbox verification | Cross-message assembly and signature checks are implemented and tested locally; the final Meta round trip necessarily follows hosting. |
| KMS-routed proactive WhatsApp escalation | Encryption, decryption, multi-reporter delivery and fallback update storage are implemented; the key exists and its environment binding awaits the explicitly approved security update described above. |
| SES notification | Application support is complete; sender/recipient verification is an AWS-account operational prerequisite. |
| Live Meta WhatsApp round trip | Requires the account's Meta App Secret and a newly rotated WhatsApp access token. |

## Intentionally not claimed as complete

| Item | Reason |
|---|---|
| Real municipal complaint integration | Both specifications permit a clearly labelled simulated authority for the prototype; official APIs are municipality-specific. |
| Cognito, AgentCore Gateway/managed Memory, Rekognition | Optional production expansion in the CivicFix document. The required AgentCore Runtime adapter is prepared; Lambda/API Gateway/JWT remain the primary channel runtime. |
| Multi-city self-service onboarding, billing, IoT and predictive maintenance | Explicit non-goals or future expansion, not MVP acceptance criteria. |
| Officer performance scoring by name | Explicitly prohibited by the WardWatch specification. |

## Explicitly deferred (not silently dropped)

- **JWT secret rotation, KMS alias binding, API timeout bump** — as this
  document already states, rotating the live secret invalidates every issued
  officer/admin token; this remains pending explicit approval. The Secrets
  Manager template resource above is prepared for that moment but not wired
  live.
- **Live Meta WhatsApp round trip, SES sender/recipient verification, applying
  the Cognito IaC to the live pool** — these require real AWS/Meta account
  actions (verifying identities, rotating tokens, running `sam deploy`)
  outside what a code change can complete or "verify" on its own.
- **Dashboards, lifecycle state machine, dedup/routing/priority/AI
  verification** — re-audited and confirmed genuinely implemented and tested;
  left unchanged.
- **DynamoDB Streams / WebSocket push** — the current polling-with-timestamps
  approach is the documented fallback this project's own requirements allow;
  no evidence surfaced that it is unreliable, so it was not spec­ulatively
  replaced.

### AWS account prerequisites to close the remaining items

1. Approve and apply the JWT secret rotation + KMS alias binding + API timeout
   update (`infra/template.yaml`, already staged pre-existing pending change).
2. Verify SES sender/recipient identities in the `ap-south-1` account.
3. Supply a rotated Meta WhatsApp access token and confirm the App Secret for
   the production number.
4. Review and apply the new Cognito `template.yaml` resources with
   `sam deploy`, then retire the standalone `infra/cognito-user-pool.json`
   / `infra/runtime-additions-policy.json` files once confirmed equivalent to
   the live pool.

### Commands

- Backend tests: `cd backend && python -m pytest`
- Frontend type check: `cd frontend && npx tsc --noEmit`
- Frontend production build: `cd frontend && npm run build`
- Infra diff (no deploy): `cd infra && sam build && sam deploy --guided --no-execute-changeset`

## Specification conflicts resolved

- WardWatch says WhatsApp is the entire citizen interface, while CivicFix requires
  a React citizen UI. Both channels are retained; WhatsApp remains the primary
  flow and the web report page is an optional CivicFix extension.
- CivicFix describes public nearby issues and evidence, while WardWatch forbids
  individual public complaint fields. Nearby discovery therefore returns opaque
  community summaries only. Exact records and photos require the reporter token.
- The WardWatch inventory calls the orchestrator a model caller but also states
  that only three of seven components call models. The live lifecycle stays
  deterministic, while a Strands orchestrator wrapper remains available for the
  agent demonstration. This preserves the stated cost and safety model.
