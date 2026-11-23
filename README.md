# Briqen AI — Creator Studio Backend Architecture

This repository contains **Ashmeet Singh Sandhu**'s backend architecture submission for Briqen AI's first-round architecture exercise.

> **Disclaimer:** This repository represents an architecture and design exercise focused on system reliability, distributed concurrency, and fault tolerance. It is not an official implementation or production deployment of Briqen's internal systems.

---

## Overview

The proposed design models the core backend for an AI-assisted marketing script-to-video platform (Briqen Creator Studio). It details how to safely handle long-running generative AI pipelines (LLMs, text-to-image, and text-to-video), external provider failures, ambiguous network timeouts, and concurrent webhooks without data loss or duplicate customer charges.

### Key Architectural Topics Covered

1. **Asynchronous Script-to-Video Workflow:** Protocol returning `202 Accepted` + status URLs for multi-minute generation tasks, decoupled from client HTTP lifecycles.
2. **PostgreSQL as Canonical Source of Truth:** Durable state management for projects, immutable script revisions, scenes, jobs, attempts, billing ledgers, and export snapshots.
3. **Transactional Outbox Pattern:** Atomic DB commits pairing state updates and outbox events, preventing dual-write inconsistencies.
4. **Queue-Based Asynchronous Workers:** Reliable at-least-once task dispatching to worker pools handling external provider orchestration.
5. **AI Image & Video Generation Jobs:** Strict separation between logical user generation actions (`action_id`) and individual external provider execution attempts (`attempt_id`).
6. **Object Storage for Media Bytes:** Offloading binary media (S3/GCS) with immutable content keys and serving via short-lived signed URLs.
7. **Idempotent Generation Actions:** Guaranteeing at-most-once business effects and preventing duplicate customer charges across retries and duplicate webhooks.
8. **Retry vs. Deliberate Regeneration:**
   - *Retry:* Reuses existing `action_id`, preserves current generation epoch, incurs **zero new customer charges**, and reconciles ambiguous timeouts.
   - *Deliberate Regeneration:* Allocates a new `action_id`, increments the scene's generation epoch, and reserves a new credit charge.
9. **Late Generation Result Handling:** Deterministic, race-safe result acceptance where the first valid attempt to commit wins, while delayed or duplicate provider callbacks are cataloged as unselected assets for auditability.
10. **Epoch & Version Fencing:** Concurrency guard ensuring older, slow, or superseded generation jobs cannot roll back newer accepted assets.
11. **Billing & Credit Idempotency:** Database-level unique constraint on `credit_ledger.action_id` ensuring exactly one charge reservation, capture, or release per user action.
12. **Asynchronous Video Export:** Frozen snapshot isolation capturing ordered scenes, asset IDs, and durations to guarantee export reproducibility regardless of ongoing timeline edits.

---

## Repository Contents

```
briqen-ai-backend-architecture/
├── README.md                                 # Overview & repository documentation
├── Briqen_Backend_Architecture_Submission.md # 2-page source submission document
├── Briqen_Backend_Architecture_Submission.pdf# Compiled 2-page submission PDF
├── Briqen_AI_Appendix.md                     # AI disclosure, prompt excerpts & verification notes
└── build_pdf.py                              # Automated PDF build & 2-page verification script
```

---

## Building the Submission PDF

The submission PDF is compiled using headless Chromium/Edge with exact print stylesheets and verified for strict two-page geometry using PyMuPDF:

```bash
python build_pdf.py
```

---

## Author

**Ashmeet Singh Sandhu**  
- Email: [sandhuasmeet40@gmail.com](mailto:sandhuasmeet40@gmail.com)  
- GitHub: [@ASHMEET555](https://github.com/ASHMEET555)  
- Portfolio: [https://ashmeet.tech](https://ashmeet.tech)
