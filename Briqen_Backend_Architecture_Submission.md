# Briqen Creator Studio — Backend Architecture Submission

**Role:** Senior Backend Architect Exercise | **Focus:** Reliability, Idempotency & Provider Fault Tolerance  
**Candidate:** Ashmeet Singh Sandhu | **Email:** sandhuasmeet40@gmail.com | **Repository/Work:** [briqen-ai-backend-architecture](https://github.com/ASHMEET555/briqen-ai-backend-architecture)

---

### 1. System Architecture & Source of Truth

```
[ Creator Studio Web Client ]
       │            ▲
 (HTTP REST/SSE) (Signed URLs)
       ▼            │
[ API Gateway / Auth Service ] ──(Atomic Tx)──► [ PostgreSQL (Canonical Source of Truth) ]
       │                                         ├── Projects, Script Revisions (Immutable)
       │ (Enqueues via Outbox)                   ├── Scenes, Generation Jobs, Job Attempts
       ▼                                         ├── Credit Ledger (action_id unique), Exports
[ Outbox Dispatcher ] ──► [ Durable Queue ]      └── Transactional Outbox Events
                                │
                        (At-Least-Once)
                                ▼
                     [ Worker Pool / Orchestrator ]
                       │              │              │
                       ▼              ▼              ▼
                 [ LLM Service ] [ Image API ]  [ Video API ] ──► [ Render / FFmpeg ]
                       │              │              │                  │
                       └──────────────┼──────────────┴──────────────────┘
                                      ▼
                        [ Object Storage (S3 / GCS) ] ◄── (Raw Media Bytes)
                                      ▲
                                      │ (Ingests / Verifies)
[ Provider Webhooks / Poller ] ──► [ Idempotent Result Handler ] ──► [ DB Commit ]
```

- **Canonical Source of Truth:** PostgreSQL is the single durable authority for project topology, immutable script revisions, scenes, generation jobs, provider attempts, billing ledgers, and export snapshots. Redis/queues hold ephemeral delivery tasks only; losing queue state never corrupts workflow integrity.
- **Media Storage:** Object storage (S3/GCS) stores raw media bytes (images, video clips, renders) under immutable content keys (`/workspaces/{ws}/assets/{asset_id}.mp4`). PostgreSQL stores only verified asset metadata, checksums, and storage URIs. Access is granted via short-lived signed URLs.
- **Transactional Outbox:** Jobs, credit ledger reservations, and outbox records commit in one ACID transaction. A reliable publisher drains the outbox to durable queues (Cloud Tasks/SQS). Consumers treat delivery as at-least-once with strict idempotency.

---

### 2. Data Model & State Ownership

| Record Entity | Key Attributes & State Ownership |
| :--- | :--- |
| **`projects`** | `id`, `workspace_id`, `owner_id`, `edit_version`, `status`. Scopes all sub-entities to authenticated tenants. |
| **`script_revisions`** | `id`, `project_id`, `revision_no`, `content`, `parent_revision_id`. **Immutable** script history. Unique `(project_id, revision_no)`. |
| **`scenes`** | `id`, `project_id`, `position`, `duration_ms`, `selected_asset_id`, `generation_epoch`, `active_generation_job_id`. |
| **`generation_jobs`** | `id`, `action_id` (Unique), `scene_id`, `generation_epoch`, `kind` (`IMAGE`/`VIDEO`), `status`, `input_hash`. **Owns logical job state.** |
| **`job_attempts`** | `id`, `job_id`, `attempt_no`, `provider_request_id` (Unique), `provider_idempotency_key`, `status`, `error`. |
| **`assets`** | `id`, `project_id`, `scene_id`, `storage_uri`, `checksum`, `mime_type`, `dimensions`, `duration_ms`. **Immutable media metadata.** |
| **`credit_ledger`** | `id`, `action_id` (Unique), `workspace_id`, `amount`, `state` (`RESERVED` \| `CAPTURED` \| `RELEASED`). **Guarantees 1 charge/action.** |
| **`exports`** | `id`, `project_id`, `frozen_snapshot` (JSONB ordered scenes, asset IDs, durations), `status`, `output_asset_id`. |

---

### 3. Two-Scene Lifecycle Trace (Asynchronous Protocol)

1. **Script Ingestion & Splitting:** User drafts script in Project `P1`; system writes immutable revision `R1`. Calling `/projects/{id}/scenes:split` creates stable scenes `S1` and `S2` tied to `R1`.
2. **Asynchronous Execution Protocol:** User requests Image for `S1` and Video for `S2`. Generating takes 10s–60s+. The API immediately returns:  
   `HTTP/1.1 202 Accepted`  
   `{"job_id": "job_s1", "status": "QUEUED", "status_url": "/api/v1/generation-jobs/job_s1"}`  
   Database atomically records `generation_jobs`, reserves credits in `credit_ledger`, and writes outbox events. The client polls `status_url` with backoff or subscribes to server-sent events (SSE). State survives client disconnection.
3. **Scene 1 Success:** Worker invokes Image API, streams bytes to Object Storage (`ast_img_1`), writes metadata to `assets`, marks `job_s1` as `SUCCEEDED`, captures ledger reservation, and sets `S1.selected_asset_id = ast_img_1`.

---

### 4. Failure Handling, Provider Timeouts & Race Conditions

1. **Scene 2 Ambiguous Timeout:** Video provider call for `S2` times out at worker boundary. **A timeout is NOT proof of failure; provider may still be processing.** Worker flags attempt as `UNKNOWN`/`RECONCILING`.
2. **Isolation Guarantee:** `S1`'s accepted image remains untouched. Scenes are fully decoupled; failures in `S2` cannot corrupt or reset `S1`.
3. **User Retry Handling:** User clicks "Retry". The client submits retry with original `action_id`. System reuses the existing `generation_jobs` row and existing `RESERVED` ledger record—**zero duplicate charges**.
4. **Pre-Flight Status Check:** Worker queries provider API with `attempt_1.provider_request_id`. If running, worker waits. If provider lacks queryability, worker dispatches `attempt_2` reusing the stable `provider_idempotency_key`.
5. **Race-Safe Late Callback Resolution:** If Attempt 2 succeeds and commits first, its asset is promoted. If Attempt 1's callback arrives later, the handler validates the signature, stores media as an **unselected asset** for auditing, but cannot overwrite `S2.selected_asset_id` because `job_s2.status` is already `SUCCEEDED`. **First valid success to commit wins.**

---

### 5. Retry vs. Deliberate Regeneration

| Feature | Retry (Transient Failure Recovery) | Deliberate Regeneration (New Creative Variant) |
| :--- | :--- | :--- |
| **Trigger & Intent** | User recovers failed/timed-out generation. | User requests new visual direction for scene. |
| **Action & Ledger ID** | Reuses original `action_id` & existing ledger row. | Allocates new `action_id` & creates new ledger row. |
| **Customer Billing** | **No additional charge** (captured or released once). | **Billed as new charge** (new credit reservation). |
| **Generation Epoch** | Preserves current `scene.generation_epoch`. | Increments `scene.generation_epoch` (`e = e + 1`). |
| **Active Scene Display** | Current asset (if any) remains visible. | Previous asset stays visible until new job commits. |
| **Stale Fencing** | Cannot overwrite higher generation epochs. | Fences out and ignores late results from prior jobs. |

---

### 6. Core Pseudocode: Retry & Race-Safe Result Acceptance

```python
def retry_job(job_id: str) -> Job:
    with db.transaction():
        job = db.select_for_update("generation_jobs", id=job_id)
        if job.status == Status.SUCCEEDED: return job
        attempt = db.get_latest_attempt(job.id)
        if attempt.status == Status.UNKNOWN and provider.supports_status_lookup:
            status, asset_data = provider.check_status(attempt.provider_request_id)
            if status == Status.RUNNING: return job
            if status == Status.SUCCEEDED: return accept_result(job.id, attempt.id, asset_data)
        if attempt.status == Status.UNKNOWN and not provider.supports_idempotency_key:
            job.update(status=Status.RECONCILING); return job
        enqueue_outbox(event="RETRY_ATTEMPT", job_id=job.id, action_id=job.action_id)  # No new charge
        return job

def accept_result(job_id: str, attempt_id: str, payload: dict) -> bool:
    asset = object_storage.put_and_record_metadata(payload)  # Immutable write
    with db.transaction():
        job = db.select_for_update("generation_jobs", id=job_id)
        scene = db.select_for_update("scenes", id=job.scene_id)
        # Epoch fencing & terminal state guard: first valid success wins
        if (job.status in {Status.RUNNING, Status.UNKNOWN, Status.RECONCILING}
                and scene.active_generation_job_id == job.id
                and scene.generation_epoch == job.generation_epoch):
            job.update(status=Status.SUCCEEDED, selected_asset_id=asset.id)
            scene.update(selected_asset_id=asset.id)
            db.execute("UPDATE credit_ledger SET state = 'CAPTURED' WHERE action_id = %s", job.action_id)
            return True
        asset.update(status="UNSELECTED_SUPERSEDED")  # Harmlessly retain for audit
        return False
```

---

### 7. MVP Release Scope, Pre-Ship Verification & Critical Assumption

- **Included in MVP:** Workspace-isolated CRUD; immutable script revisions; scene split/reorder; asynchronous image/video dispatch with transactional outbox; provider adapters with timeouts; immutable asset storage; idempotent credit ledger; atomic epoch-fenced result promoter; frozen-snapshot FFmpeg video stitcher.
- **Explicitly Deferred:** Multi-model routing/fallbacks, real-time multi-user collaborative canvas, complex video transitions/multi-track audio mixer, autoscaling worker mesh, and advanced prompt evaluation pipelines.
- **Two Mandatory Pre-Ship Verification Checks:**
  1. *Fault-Injection & Callback Race Test:* Trigger artificial provider 60s timeout, fire immediate user retry, and inject out-of-order webhooks from both attempts simultaneously. Verify database contains exactly one `CAPTURED` ledger row, `S1` asset remains intact, and `S2` retains winning asset without corrupting scene epoch.
  2. *Immutable Export Snapshot Isolation Test:* Initiate video export on a 2-scene timeline. Concurrently reorder scenes, edit durations, and delete a scene during active rendering. Verify final output video strictly reflects the frozen snapshot taken at export initiation.
- **Single Critical Assumption That Could Change Design:** Generation providers offer reliable status queries or idempotent request deduplication. If a third-party provider provides neither, automated retries after ambiguous timeouts cannot guarantee zero duplicate upstream vendor billing; the system must transition the job to manual user reconciliation.

---

### 8. Relevant Prior Work & Authoritative References

- **Assignment Design Artefacts:** [https://github.com/ASHMEET555/briqen-ai-backend-architecture](https://github.com/ASHMEET555/briqen-ai-backend-architecture)  
  *(Contains the design specification, automated PDF generation pipeline, and verification traces for this architecture exercise).*
- **Authoritative Engineering Standards Applied:**
  - *Briqen MI Public Product Framing:* Marketing intelligence, campaign scripts & video rendering ([Briqen Product](https://briqen.com/)).
  - *AWS Well-Architected Framework:* Idempotent mutating operations via client request tokens ([AWS Idempotency](https://docs.aws.amazon.com/wellarchitected/2025-02-25/framework/rel_prevent_interaction_failure_idempotent.html)).
  - *AWS Builder’s Library:* Addressing ambiguous timeouts with jittered backoff ([AWS Timeouts & Retries](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)).
  - *AWS Architecture Patterns:* Transactional Outbox pattern for reliable event publishing ([AWS Outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)).
  - *Google Cloud Architecture:* At-least-once delivery semantics in distributed queues ([GCP Cloud Tasks](https://cloud.google.com/tasks/docs/dual-overview)).
  - *Temporal Architectural Guide:* Activity idempotency and asynchronous completion ([Temporal Activities](https://docs.temporal.io/activities)).
