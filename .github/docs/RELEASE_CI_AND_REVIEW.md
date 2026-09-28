# Main public profile: CI, release evidence and review gates

Scope: `geni2kim-ai/Maestro-prep`, `main`, `0.1.0-public-redacted-hotfix`. This page documents the **initial public-redacted profile** only. It does not promote the separate Draft candidate.

## 1. Main CI

The initial `main` tree had no `.github/workflows` directory. The existing four-platform Draft workflow cannot be treated as a main run. The added `candidate-ci.yml` starts on main push, PR into main and manual dispatch. It runs Python 3.11 and 3.13 on Ubuntu and Windows using SHA-pinned GitHub actions and read-only permissions. Its **main-only** runner validates the manifest and checksums, public privacy, the included redacted component pin, coordinator tests, included component tests and 20-case synthetic replay. No live routing, host installation or external component is invoked. The workflow itself is checkout control metadata, not part of the 40-file public payload.

The manifest scanner explicitly sorts by POSIX path strings (not platform-specific `Path` ordering), so Windows and Unix agree on the same 40-file sequence. The root `.gitattributes` uses byte-exact `-text` checkout to prevent Windows newline conversion from invalidating pinned source and inventory hashes. It is repository control metadata, not a distributed release file. The package verifier allows only the precisely named hotfix feedback and evidence Markdown as external control records, plus Git/CI metadata and generated Python caches. Unexpected additional application files remain a manifest mismatch. Exclusion is not evidence of archive authenticity: a received distribution still needs its archive SHA-256 from an independent owner-controlled channel.

## 2. Badges and run provenance

At inspection, the actual `main` README had **no** CI or release badge, contrary to the historical feedback description. Do not display a Draft PR badge as a main result. Main remains badge-free until an exact main run ID, commit SHA and matrix conclusions are verified. An added workflow file is not itself a passing CI receipt; consult the main-specific Actions URL for the run.

## 3. External planning reference conformance

Neither the inspected pre-privacy parent of commit `b38f2c7` nor that privacy commit's changed-file list contains a `.github/workflows` file on main. Thus the available main history does **not** substantiate the claim that this commit removed a Public Astra reference conformance workflow. The Draft contains `candidate-ci.yml`, which is a different profile and must not be copied wholesale to main. In this initial public profile, synthetic planning-contract and manifest/pin checks are the available substitute **only for public offline compatibility**. A production external-reference conformance claim requires independently obtained approved reference bytes, schema/profile and source hashes, owner approval, a separate test harness with negative controls, and a recorded exact-commit report. That gate remains `NOT_RUN`; it is not silently replaced by synthetic tests.

## 4. Release evidence re-execution

For this source profile run `python .github/scripts/main_ci.py` locally or in the main CI matrix. Its JSON report includes per-check exit codes and test counts. The historical `RUN_REPORT.json` records producer-reported local baseline results; do not re-label it as newly executed or as a signed release artifact. Record actual fresh command outputs, SHA, platform and time in `evidence/evidence_v0.1.0-public-redacted-hotfix.md`. Manifest validation covers checkout distributable bytes, **not** a newly built release ZIP or externally signed checksum. A full release archive authenticity gate additionally requires assembling immutable release bytes and comparing the archive SHA-256 against an independently delivered trusted value. Until that is done, archive authenticity is `NOT_RUN`.

## 5. Draft PR disposition

Draft PR #1 (`fix/leonardo-connection-v0.2`) remains a separate newer candidate. It has additional functionality and a different CI runner. **No merge is authorized by this feedback**, and the change is intentionally limited to hotfixing main's initial profile. Revisit promotion only with an explicit owner decision, a refreshed branch diff, independent privacy/security review of all added code and history, source inventory regeneration and clean tests on the exact proposed merge head.

## 6. Independent review and authority

An automated first-party/main CI result is self-test evidence, **not** independent red-team review and not permission to deploy. Independent review becomes eligible only when the owner appoints a separate reviewer, provides the exact immutable source/manifest and external evidence bundle, and records the review request identity, methods, findings and non-final adjudication. Actual host integration requires separately approved vendor/source pins, authorized local execution receipts, rollback plan and owner authorization. The public repo does not gain runtime, host mutation, deployment or independent-review authority from a green CI result.

## 7. Owner-triggered release archive assembly (F1 follow-up)

`.github/workflows/release.yml` is manual-only (`workflow_dispatch`). The job is gated on main, the repository owner GitHub actor and an explicit assembly checkbox. Only the owner should select **Actions → Owner-triggered candidate release assembly → Run workflow → main**. This checkbox approves assembly, **not** public release, host integration or deployment. This work does not dispatch the workflow.

Once the owner triggers it, the job runs complete main public CI (including synthetic release-builder tests) and uploads an Actions artifact containing: a byte-stable ZIP with exactly **40 manifest-listed payload files + MANIFEST.json + SHA256SUMS.txt** (42 members), a separate copy of `SHA256SUMS.txt`, and a whole-archive `.zip.sha256` text record. The script refuses overwrite and destinations inside the checkout. `.github` and the exact feedback/evidence control records are excluded from the 40-file payload.

Actions artifacts and an in-band SHA256 record do not certify independent archive authenticity. The owner must publish the full archive SHA256 by a **separately controlled channel**, independently acquire the ZIP and compare exact bytes before changing `owner_out_of_band_digest_comparison=NOT_RUN`. No GitHub Release/tag is published by this workflow. Independent archive authenticity remains `NOT_VERIFIED` until the owner completes these external steps.

## 8. Owner-gated external reference conformance (F2 follow-up)

The manual-only `.github/workflows/external-conformance-draft.yml` deliberately requires the owner GitHub actor, main branch, owner checkbox and a separately provisioned **isolated self-hosted runner**. Source archives, owner pins, schemas, validator and trusted harness are **not** in this repository. [Owner pin request and checklist](OWNER_PIN_REQUEST.md) records all exact required bytes/hashes and runner prerequisites; [unfilled template](EXTERNAL_REFERENCE_PIN_TEMPLATE.json) is intentionally invalid until owner supplies values. The gate script checks all six external file SHA-256 pins, archive entry byte bindings, exact main commit and a distinct trusted harness hash. Owner-controlled semantic harness must furnish positive and negative-case results in a strict, non-authoritative receipt. The checked-in tests exercise only synthetic validation/fail-closed behavior. No owner-run dispatch was performed here: external conformance remains `NOT_RUN`.

## 9. Separate red-team work order (F3 follow-up)

[Independent red-team checklist — DRAFT](RED_TEAM_CHECKLIST_DRAFT.md) identifies 12 adversarial probes, independent evidence custody, accepted verdict vocabulary and explicit owner/reviewer separation. This assistant **authored the checklist only** and did not conduct independent red-team execution, submit a verdict or acquire review authority. Actual execution and adjudication remain `NOT_RUN` / `NOT_GRANTED` pending assignment of a distinct reviewer.

## 10. Owner-commissioned ChatGPT source and workflow robustness review

This repository may receive an owner-commissioned ChatGPT review of the current checkout's source and workflow. Since ChatGPT also authored the prior checklist, such a review is **same-lineage**, not a claim of an organizationally independent human or agent assessment. The reviewer may correct directly verifiable source defects and record exact-commit main CI and synthetic fixtures. Review findings, skips and out-of-scope owner steps are documented separately in `evidence/evidence_v0.1.0-public-redacted-hotfix_redteam1.md`. Current-file scanner covers UTF-8, binary ASCII fragments and UTF-16 (either byte alignment), but does **not** authenticate historical Git objects, encrypted/compressed opaque blobs or archive provenance. Owner release digest comparison, approved external reference and host review remain separate.

### Source-only boundary-condition follow-up for the reference gate

The local pin gate now rejects ambiguous repeated JSON keys and non-finite values, imposes explicit JSON/archive size limits, checks archive member file types and rechecks owner-pinned source, pin and harness bytes after the separately authorized harness returns. The output receipt uses exclusive creation. Nine repository-local synthetic checks exercise these boundaries; they are not evidence that an owner-supplied external reference, authorized runner or separately approved harness was actually used. Actual external conformance remains NOT_RUN until those prerequisites exist.
