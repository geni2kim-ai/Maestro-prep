# Maestro-prep owner gates — sequential handling evidence

- **Repository:** `geni2kim-ai/Maestro-prep` (owner named in request: **Genie Kim**). All writes described here were confined to this repository. The public `geni2kim-ai/astra-prep` candidate was inspected **read-only** in step 2; it was not modified or run.
- **Procedure:** address gate 1 first, then the pin proposal (gate 2), then the separate-reviewer handoff (gate 3). Distinguish a prepared deliverable from actual owner-controlled execution or approval.
- **Date:** 2026-09-28; original Maestro-prep source at intake: `362f070cae899f391331405e5c93a89c40999a8c`.
- **After step 2:** commit [`3796e8e29fe518ccd41a063fc49c6e86ac3930a0`](https://github.com/geni2kim-ai/Maestro-prep/commit/3796e8e29fe518ccd41a063fc49c6e86ac3930a0), [CI 36376386397](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36376386397) completed/success.
- **After step 3, before this evidence publication:** commit [`2db7ad2ae51ab7cbdab39dd1850ccc2cd87066c3`](https://github.com/geni2kim-ai/Maestro-prep/commit/2db7ad2ae51ab7cbdab39dd1850ccc2cd87066c3), [CI 36376465505](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36376465505) completed/success on Ubuntu and Windows, Python 3.11/3.13 (4/4 jobs). These are *ordinary push CI runs*, not the manual release or conformance jobs.
- **Package invariant:** the existing public distributable manifest stays at 40 entries; `MANIFEST.json` Git blob `d92492b93d1feb164f5e37b307345c0e709a48b0`, raw SHA-256 `2035a8ca8277ff5d741dfc5ef8c0a0949910f7946b7360265aebb2f893e6500a`. The new handoff and proposal under `.github/docs/` and this precisely excluded evidence path are repository-control documents, not the 40 payload files.

## Gate 1 — `release.yml` manual dispatch attempt

**Attempted:** inspected [the exact release workflow](../.github/workflows/release.yml) (Git blob `1b08821bf9d9d564272f3088c0bb0e1ffff6d14d`), discovered available actions exposed by the connected GitHub app, inspected available recent repository workflow runs, and checked the workflow guard. The workflow requires `github.ref == refs/heads/main`, `github.actor == geni2kim-ai` and boolean `inputs.owner_approved_assembly == true`; it only has `contents: read` permission and attaches a candidate 40-file ZIP plus manifest/checksum files after offline checks.

**Actual outcome:** `BLOCKED_TOOL_CAPABILITY / NOT_RUN`. The connected GitHub actions available in this chat include GET/re-run of *existing* jobs but provide **no new `workflow_dispatch` operation**. No manual dispatch request was sent to GitHub, no GitHub job was created by this step, and therefore no actor-rejection status or other GitHub dispatch failure is claimed. The inspected latest repository run list contained ordinary main push CI receipts; these are not release-assembly receipts.

**Owner follow-up:** **owner가 GitHub Actions UI에서 직접 실행해야 함.** Open [Owner-triggered candidate release assembly](https://github.com/geni2kim-ai/Maestro-prep/actions/workflows/release.yml), select **Run workflow → main → `owner_approved_assembly=true`** using the authorized `geni2kim-ai` account. Record actual workflow run ID, `head_sha`, actor, job conclusion, artifact retention and exact candidate ZIP and `.zip.sha256`. The owner must send the full ZIP digest by a **separately controlled channel** and compare independently acquired ZIP bytes; `--verify-archive` can only verify against the supplied value, not certify the origin of that value.

**Remaining:** Owner manual run `NOT_RUN`; no Owner release ZIP artifact was obtained; independent digest comparison `NOT_RUN`; archive authenticity `NOT_VERIFIED`; release/deployment authority `NOT_GRANTED`.

## Gate 2 — Astra reference conformance candidate pins and approval request

**Attempted:** inspected the Maestro-prep external planning contract, owner pin request/template and the fail-closed owner gate. Searched for a likely public Astra planning reference and **read only** the matching public `geni2kim-ai/astra-prep` source at immutable commit [`54b0444002613309a6a47af281aa70f69202bd6d`](https://github.com/geni2kim-ai/astra-prep/tree/54b0444002613309a6a47af281aa70f69202bd6d) (the repository describes itself as v7.1). Recomputed raw SHA-256 for **four** exact GitHub files. This is a source *proposal*, not identification or approval of the original installed owner reference.

**Prepared:** [`.github/docs/ASTRA_PIN_PROPOSAL_20260928.md`](../.github/docs/ASTRA_PIN_PROPOSAL_20260928.md), Git blob `36785d74d4ff56b3d8feb5a4544849b010d2aeff`. The following are proposed public **source-file** SHA-256 values, not final owner-approved pins:

| Pin role | Candidate exact-source path | SHA-256 read/recomputed from pinned GitHub bytes | Status |
| --- | --- | --- | --- |
| `skill_contract` | `SKILL.md` | `dd68bae63896c955fd0de59d255c85fa8c018ad955a7d53c006bc10e4f0a9d57` | `OWNER_APPROVAL_PENDING` |
| `schema` | `schemas/prework-plan.schema.json` (byte-preserving future `schema.json`) | `8bdd1597632547f44f06c8ac3e30399342f77e1c139bad477c61086326e3c197` | `OWNER_APPROVAL_PENDING` |
| `validator` | `scripts/validate_prework.py` (byte-preserving future `validator.py`) | `f1feb40e93aa7d8c46ed48352b5ef36b112538033787b208dc7df3a687e5cf8d` | `OWNER_APPROVAL_PENDING` |
| `profile` **source candidate only** | `profiles/ai-maestro.md` | `6095a6eb7b2dc731b89f1e93349d914353abe017790152254e0bed0a2e372048` | Markdown only; **NOT a `profile.json` hash**. Owner must approve a canonical JSON profile and its actual bytes. |
| `reference_archive` | Owner-chosen frozen exact reference ZIP | **UNAVAILABLE** | Owner must select membership, provenance, exact ZIP bytes and its whole-ZIP SHA-256. |
| `bundle_manifest` | Fresh `OWNER_APPROVED_REFERENCE_BUNDLE_V1` over the *actual approved ZIP* | **UNAVAILABLE** | Owner must regenerate exact member paths/sizes/hashes and manifest byte SHA-256 after approving/archive assembly. |

**Observed mismatch requiring owner attention:** `CANDIDATE_HASHES.json` in the public source is a historical, producer-reported 25-file manifest. In the four-file spot-check, public exact-commit profile and schema hashes matched it, but `SKILL.md` and `scripts/validate_prework.py` did **not**: the historical producer values for these two files were `c35b8929bc88f6cb76d695340c2ee03e660b6a78e09de42840683085bb63f29b` and `f12bd849beeed5a77e132511f8e7a48a4adab1dcc3f617c0de4a1d220490a1a7`, respectively. The Git blob API returned identical content for the two checked public files. No cause or time of this discrepancy was established, and **the remaining 21 entries were not exhaustively checked**. Do not treat a producer-reported historical aggregate as current independent byte evidence.

**Owner approval requested:** decide whether the exact public v7.1 commit or another separately controlled original installation is authoritative; approve/replace the raw-source candidate files, provide the real approved `profile.json`, immutable `reference_archive.zip` with a **fresh** complete `bundle_manifest.json`, and pin a **separately owner-approved** trusted `owner_harness.py` SHA-256. Record exact final Maestro source commit, non-placeholder `owner_approval_id`, `OFFLINE_REFERENCE_CONFORMANCE_ONLY` scope, expected negative/positive tests and separately approved isolated `[self-hosted, maestro-owner-approved, isolated]` runner. Keep filled pins and reference source bytes in an approved private handoff, not committed to this public-profile repository.

**Actual outcome:** `PIN_CANDIDATES_DOCUMENTED / OWNER_APPROVAL_PENDING`. No owner-approved external reference bytes, private pin, harness or approved runner were supplied; no external conformance workflow was dispatched. `external_reference_conformance=NOT_RUN`.

## Gate 3 — independent reviewer assignment handoff

**Attempted:** prepared a separate reviewer work packet using the checked-in F3 checklist and the previous same-lineage ChatGPT R1 evidence. No real reviewer identity or consent was supplied, and this task does not self-designate a reviewer.

**Prepared:** [`.github/docs/OWNER_INDEPENDENT_REVIEW_PACKET_20260928.md`](../.github/docs/OWNER_INDEPENDENT_REVIEW_PACKET_20260928.md), Git blob `7051213b7ae9b855d7cb555936725955520b3d12`. It specifies immutable review target source [`3796e8e29fe518ccd41a063fc49c6e86ac3930a0`](https://github.com/geni2kim-ai/Maestro-prep/tree/3796e8e29fe518ccd41a063fc49c6e86ac3930a0) (or a *new exact commit only if owner explicitly rebinds*), 40-file manifest and checksum identities, exact F3 checklist Git blob `23bddffc92872b61da929905dfd9acfafeb5564f`, prior same-lineage R1 review Git blob `2299411560866080170573a3d0f8afe23e444e6a`, current proposal blob and the matching exact-source CI. It also states the bounded review scope, independent acquisition of source bytes and hashes, a separate reviewer's environment/tool logs, 12-item evidence-based `PASS/FINDINGS/BLOCKED/NOT_RUN` method, severity and reproducibility fields, untested owner gates and non-final owner adjudication.

**Owner nomination requested:** name a **different human or distinctly appointed agent**, attest relevant separation from ChatGPT's prior checklist drafting and R1 source review, choose the **exact review target commit**, grant only the approved source-and-workflow review and isolated synthetic-test methods, transmit frozen inputs through a controlled channel, and preserve the reviewer ACK, independent raw observations, per-item verdict and owner adjudication. Merely using another chat route does not prove independence.

**Actual outcome:** `REVIEW_PACKAGE_PREPARED / REVIEWER_NOT_ASSIGNED / INDEPENDENT_REVIEW_NOT_RUN`. No reviewer was contacted, appointed or represented as having performed a review. An assignment requires a real owner decision and distinct reviewer acceptance.

## Summary and remaining owner decisions

| Gate | This pass completed | Actual owner-controlled result | Required next step |
| --- | --- | --- | --- |
| 1 — Owner release | Workflow guard checked; attempted tool capability discovery, documented why dispatch could not be sent | `BLOCKED_TOOL_CAPABILITY / NOT_RUN` | Owner manually triggers release in GitHub UI and verifies artifact digest through an independent channel. |
| 2 — Approved Astra pins | Exact public v7.1 source candidates and observed historical hash differences documented in approval request | `APPROVAL_PENDING / CONFORMANCE_NOT_RUN` | Owner selects authoritative bytes, approves full private pin, exact main commit and trusted offline harness/runner; only then manual conformance. |
| 3 — Independent review | Immutable-input reviewer handoff and owner nomination request prepared | `NOT_ASSIGNED / INDEPENDENT_REVIEW_NOT_RUN` | Owner names a different human/agent, explicitly binds its input snapshot and records its separate acceptance/results. |

**Boundary:** `candidate_only=true`, `finality=non_final`, `decision_authority=none`, `external_conformance=NOT_RUN`, `independent_review=NOT_RUN`, `release_archive_authenticity=NOT_VERIFIED`, `deployment_authorized=false`. Preparing these three gates and publishing this document does **not** complete owner manual runs or constitute their approval. This evidence-only publication creates a new Git commit; its exact-head main CI must be checked separately and must **not** be mistaken for a manually dispatched Owner release or real external conformance receipt.
