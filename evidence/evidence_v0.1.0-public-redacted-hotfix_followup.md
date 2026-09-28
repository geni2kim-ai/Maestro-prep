# Evidence: v0.1.0-public-redacted-hotfix follow-up (F1–F3)

- **Repository:** `geni2kim-ai/Maestro-prep`, main only; no Leonardo repository changes.
- **Feedback read before work:** `feedback/feedback_v0.1.0-public-redacted-hotfix_followup.md`, Git blob `536110075947600f7264a0a465ab027a7a8bdc81`.
- **Version and payload:** `0.1.0-public-redacted-hotfix`, 40 manifest-listed distributable files. No Draft PR #1 merge.
- **Starting main SHA:** `a50a2b24ef5dadd60de5e8d786b33185aac82b51`.
- **F1 commit:** [80045c555341bb14641fc0f844c5305acb266883](https://github.com/geni2kim-ai/Maestro-prep/commit/80045c555341bb14641fc0f844c5305acb266883).
- **F2 commit:** [5c8087dcc02fe3d441b5b950f48c789a86472bce](https://github.com/geni2kim-ai/Maestro-prep/commit/5c8087dcc02fe3d441b5b950f48c789a86472bce).
- **F3 exact tested source SHA:** [c8725e4427a0536c348c2a12e067e6e9ef392193](https://github.com/geni2kim-ai/Maestro-prep/commit/c8725e4427a0536c348c2a12e067e6e9ef392193).
- **Exact source CI:** [run 36365605305](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36365605305), main push, created `2026-09-28T01:20:31Z`, completed SUCCESS, four of four platform jobs. Only checked-in public source and synthetic fixtures were tested.

## F1 — candidate archive assembly (source and CI complete; owner release NOT_RUN)

Created:
- [`.github/workflows/release.yml`](../.github/workflows/release.yml): manual `workflow_dispatch` **only**, main branch, named repository-owner GitHub actor, explicit assembly-only checkbox; read-only token and SHA-pinned checkout/setup-python/upload-artifact. No release tag, publish or deployment step. This workflow was **not** manually dispatched in this task.
- [`.github/scripts/build_release.py`](../.github/scripts/build_release.py): validate existing package manifest, construct a reproducible fixed-metadata `ZIP_STORED` archive of **40 manifest-listed payloads + MANIFEST.json + SHA256SUMS.txt** (42 entries), re-read and compare archived bytes, copy `SHA256SUMS.txt` and output a separate full-ZIP `.zip.sha256` digest. Refuse overwriting previous output or writing into the checkout.
- [`.github/scripts/test_release_builder.py`](../.github/scripts/test_release_builder.py): three synthetic/repository-local tests for 40 exact payload hashes and ZIP members, SHA/checksum copy, deterministic two-build output, no overwrite and checkout destination refusal. These tests produced **temporary test ZIPs**, not an owner Actions release artifact.
- [`tools/verify_package.py`](../tools/verify_package.py): precisely exclude this follow-up feedback and evidence as non-distributable control documents. Recompute verifier's SHA-256/byte length in `MANIFEST.json` and `SHA256SUMS.txt`, retaining exactly 40 distributable files; unexpected other application files still fail closed.
- Added release-builder tests to `main_ci.py`. [F1 main CI run 36365420576](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36365420576) completed SUCCESS on all four Ubuntu/Windows × Python 3.11/3.13 jobs.

**Owner gate:** manually dispatch the release workflow on an approved exact main commit, retain its actual run and ZIP artifact, publish the full ZIP digest through an **independently controlled channel**, and compare independently acquired intended archive bytes. In-band Actions SHA256SUMS and ZIP digest cannot themselves prove authenticity. `owner_out_of_band_digest_comparison=NOT_RUN`; `independent_archive_authenticity=NOT_VERIFIED` and no independently approved immutable release archive is claimed.

## F2 — external reference conformance draft and exact owner pin request (NOT_RUN)

Created:
- [`.github/workflows/external-conformance-draft.yml`](../.github/workflows/external-conformance-draft.yml): manual-only owner/main/check-box job on an **owner-provisioned isolated self-hosted runner**, not a normal CI run. No owner trigger was executed.
- [`.github/scripts/external_conformance_gate.py`](../.github/scripts/external_conformance_gate.py): fail-closed owner-approval ID and scope; exact main source commit and SHA-256 of six separate approved files: `reference_archive.zip`, `profile.json`, `schema.json`, `validator.py`, `SKILL.md`, and `bundle_manifest.json`. It checks the ZIP's bounded member set, size and SHA hashes without extraction and requires an external separately pinned owner harness. A future authorized owner-run harness must supply a strict source/receipt binding, at least one positive and two negative results, and zero failures/skips. This self-reported candidate result would still **not** constitute independent review.
- [Unfilled owner pin template](../.github/docs/EXTERNAL_REFERENCE_PIN_TEMPLATE.json) and [owner pin request](../.github/docs/OWNER_PIN_REQUEST.md): specific exact byte/source/version/provenance requirements, all six digest pins, trusted harness and its independent pin, approved exact main SHA, owner approval identifier and isolated runner setup. The template intentionally fails validation with placeholders; **do not commit filled private pins**.
- [Four synthetic negative-control unit tests](../.github/scripts/test_external_conformance_gate.py): happy-path pin validation still reports `NOT_RUN`; missing owner approval, wrong exact main SHA, mutated source bytes and unpinned harness fail closed. Added these tests to normal main CI.

**Missing owner inputs:** no externally approved source bytes, SHA/profile/schema/manifest pins, authorized trusted harness, isolated owner runner or owner permission were supplied. The manual external workflow was **not dispatched**. External reference conformance remains `NOT_RUN` rather than being inferred from synthetic tests.

## F3 — red-team checklist draft only (independent reviewer NOT_RUN)

Created [`.github/docs/RED_TEAM_CHECKLIST_DRAFT.md`](../.github/docs/RED_TEAM_CHECKLIST_DRAFT.md) with 12 explicit reviewer probes (`RT-01`–`RT-12`) covering provenance and main/Draft separation, cross-platform SHA, manual release gate, deterministic/malicious ZIPs, digest independence, artifact custody, six owner pins and harness forgery, member validation, privacy/history, authority confusion and evidence/temporal overclaims. It specifies a distinct reviewer, immutable evidence custody, command/observation receipts, per-probe `PASS/FINDINGS/BLOCKED/NOT_RUN` and owner adjudication outside this author.

Extended [`.github/docs/RELEASE_CI_AND_REVIEW.md`](../.github/docs/RELEASE_CI_AND_REVIEW.md) to document F1–F3 and all authority boundaries. **ChatGPT authored the checklist only; it did not execute an independent red-team review, provide an independent verdict or gain any review authority.** A separately appointed human or independent agent owns actual execution, findings and verdict. `independent_review=NOT_RUN`; `decision_authority=none`.

## Final exact-source, main-branch CI (eight checks in each of four jobs)

[run 36365605305](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36365605305) for SHA `c8725e4427a0536c348c2a12e067e6e9ef392193` completed **SUCCESS** in all four jobs: Ubuntu Python 3.11 (job `108751280006`), Ubuntu Python 3.13 (`108751279941`), Windows Python 3.11 (`108751279811`), Windows Python 3.13 (`108751279907`).

| Repository-local check | Ubuntu 3.11 / 3.13 | Windows 3.11 / 3.13 |
| --- | --- | --- |
| 40-file manifest + SHA256SUMS current-checkout integrity | PASS / PASS | PASS / PASS |
| Current-file privacy scan | PASS / PASS | PASS / PASS |
| Included redacted-public O-Prep source pin | PASS / PASS | PASS / PASS |
| Coordinator regressions | 30 run, 0 skipped, PASS per job | 30 run, 0 skipped, PASS per job |
| Included public compatibility regressions | 61 run, 5 skipped, PASS per job | 61 run, 6 skipped, PASS per job |
| Synthetic architecture replay | 20 matched, PASS per job | 20 matched, PASS per job |
| F1 temporary archive-builder tests | 3 run, PASS per job | 3 run, PASS per job |
| F2 synthetic pin gate tests | 4 run, PASS per job | 4 run, PASS per job |
| **Total check receipts** | **8/8 PASS per job** | **8/8 PASS per job** |

The included component's optional test skips remain disclosed; Windows has one extra POSIX-only file-mode skip. Actual host NTFS ACL verification remains `NOT_RUN`. The tests validate current public-profile bytes and synthetic behavior, not the original independently approved external component, owner-executed release artifact or real external conformance.

## Closeout boundary

F1/F2/F3 **deliverables created, committed and main CI-verified**. Owner release workflow dispatch, independent ZIP authenticity comparison, owner-provisioned external reference conformance, independent red-team execution/adjudication, real runtime and deployment are **NOT_RUN / NOT_VERIFIED / NOT_GRANTED**, as applicable. `candidate_only=true`; `finality=non_final`; `decision_authority=none`. The subsequent evidence-only publication commit adds this precisely excluded non-distributable Markdown; require a fresh exact-head CI receipt before claiming the publication commit itself passed.
