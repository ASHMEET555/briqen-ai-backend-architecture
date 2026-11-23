# Briqen AI Architecture Exercise — AI Use Disclosure & Appendix

**Candidate:** Ashmeet Singh Sandhu  
**Email:** sandhuasmeet40@gmail.com  
**Exercise:** Briqen Creator Studio — Backend Architecture (First Round)  
**Repository:** [https://github.com/ASHMEET555/briqen-ai-backend-architecture](https://github.com/ASHMEET555/briqen-ai-backend-architecture)  
**Date:** November 2026  

---

## 1. AI Assistance Disclosure

In accordance with Briqen’s submission guidelines, this document explicitly discloses the use of generative AI in completing this architectural exercise.

- **AI Tools Used:** Antigravity AI Assistant (powered by Google DeepMind’s Gemini 3.8 Flash model).
- **Scope of AI Assistance:** 
  1. Structuring and compressing the architectural design specification into a dense, submission-ready, two-page layout (`Briqen_Backend_Architecture_Submission.md`).
  2. Generating an ASCII architecture diagram representing the transactional outbox, queue, workers, storage, and callback flow.
  3. Drafting and tightening the concise 20-line pseudocode demonstrating database locks, provider idempotency pre-flight, and generation epoch fencing.
  4. Scripting automated PDF compilation and page-budget verification via headless Microsoft Edge and PyMuPDF (`fitz`).

---

## 2. Prompts Relied Upon (Excerpts)

### Prompt Excerpt 1: Architecture Invariants & Reliability Framing
> *"Produce a polished, submission-ready response for Briqen AI's first-round backend architecture exercise from the supplied plan. Ensure: PostgreSQL is the durable source of truth; separate logical user generation action (`action_id`) from provider attempts (`attempt_id`); credit ledger has a unique constraint on `action_id`; local timeout is treated as an ambiguous outcome (`UNKNOWN`), not proof of provider failure; late results are fenced by scene generation epochs; export uses frozen snapshots; fit strictly into 2 pages."*

### Prompt Excerpt 2: Pseudocode & Concurrency Rules
> *"Include 10–20 numbered or code lines implementing retry and late result acceptance. It must demonstrate the DB lock/conditional write, idempotent ledger, scene-generation fence and treatment of stale results."*

---

## 3. Key Synthesized Excerpts Relied Upon

### Synthesis Excerpt 1: Concurrency and Late-Callback Guard
```python
def accept_result(job_id: str, attempt_id: str, payload: dict) -> bool:
    asset = object_storage.put_and_record_metadata(payload)
    with db.transaction():
        job = db.select_for_update("generation_jobs", id=job_id)
        scene = db.select_for_update("scenes", id=job.scene_id)
        if (job.status in {Status.RUNNING, Status.UNKNOWN, Status.RECONCILING}
                and scene.active_generation_job_id == job.id
                and scene.generation_epoch == job.generation_epoch):
            job.update(status=Status.SUCCEEDED, selected_asset_id=asset.id)
            scene.update(selected_asset_id=asset.id)
            db.execute("UPDATE credit_ledger SET state = 'CAPTURED' WHERE action_id = %s", job.action_id)
            return True
        asset.update(status="UNSELECTED_SUPERSEDED")
        return False
```

### Synthesis Excerpt 2: Ambiguous Timeout & Pre-Flight Reconciliation
When an external video provider times out at the client/worker boundary, the provider may still finish rendering and bill the account. The system records the attempt state as `UNKNOWN` rather than `FAILED`. On retry, the worker performs a pre-flight status query using `provider_request_id` or reuses the stable `provider_idempotency_key`, preventing duplicate upstream provider spend where supported.

---

## 4. Human Verification, Critical Decisions & Adjustments by Ashmeet

The following components were personally evaluated, verified, and adjusted by Ashmeet Singh Sandhu:

1. **Rejection of Queue-Centric State:** Evaluated and reinforced that queue brokers (SQS, Cloud Tasks) and caches (Redis) must never hold the sole authoritative state of jobs. All job transitions and ledger reservations commit to PostgreSQL with transactional outbox events to ensure recovery across worker restarts.
2. **Strict Disambiguation of Retries vs. Regenerations:** Verified that a retry preserves the `action_id` and existing ledger reservation, whereas a deliberate regeneration allocates a new `action_id`, bills a new ledger charge, and increments `scene.generation_epoch`.
3. **Auditability of Superseded Assets:** Verified that late or duplicate provider results are not discarded into the void; their media is stored immutably in object storage and cataloged as `UNSELECTED_SUPERSEDED` for auditability and recovery.
4. **Physical Page Count Verification:** Ran local headless browser PDF generation and inspected page geometry with PyMuPDF (`fitz`), confirming the submission renders cleanly onto **exactly two pages** without trailing orphan lines or cut-off tables.
5. **Honest Attribution:** Verified that no fictitious repos, fake benchmark metrics, or unverified provider capabilities were included. The referenced GitHub repository was created solely to house the design artefacts, build script, and verification output for this exercise.
