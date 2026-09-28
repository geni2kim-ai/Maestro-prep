# F3 — Independent red-team review checklist (DRAFT ONLY)

**Status: NOT_RUN / reviewer NOT_ASSIGNED / decision_authority=none.** This is a work order for a separate reviewer, **not** a report of tests performed by ChatGPT. Generating, editing or internally checking this list is **not** an independent review. A different human reviewer or a separately appointed independent agent must execute it, retain its own raw observations, and issue a separate, non-final verdict. A green GitHub Actions job is self-test evidence, not this review.

## Reviewer intake and custody

Record these fields **before** inspecting or testing: review_request_id, reviewer identity, reviewer independence/dependency declaration, requested scope and excluded systems, received exact main commit SHA, exact `MANIFEST.json` bytes/SHA-256, exact checkout/archive hashes, pin-file digest if approved, UTC timestamp/timezone, source acquisition channel, tool versions, review environment and operation permissions. Retain the source snapshot read-only. Do not ingest real private reference bytes into public GitHub, and do not fetch or execute an unapproved external harness. Confirm the actual checkout differs from the author environment and that PR branch evidence is not mistaken for main evidence.

**Controls:** `candidate_only=true`, `finality=non_final`, `decision_authority=none`, `live/deploy/host_mutation=NOT_RUN` unless a separate owner-approved procedure and verified raw evidence explicitly authorize another scope. Positive local test receipts are not authority to adopt or deploy. The reviewer must not alter production, approve its own work, merge PR #1 or publish private source.

## Review probes (execute independently, in an isolated synthetic environment)

| ID | Independent adversarial check | Required primary evidence / pass condition |
| --- | --- | --- |
| RT-01 | Confirm branch/commit/feedback binding. Deliberately substitute a Draft PR commit or an older main receipt. | Exact source commit and GitHub Actions run head match. Stale or cross-branch receipts are rejected and disclosed. |
| RT-02 | Recompute distributable inventory and checksum lines from independently acquired bytes on Linux **and** Windows where available. Tamper a payload and inject an extra non-control file. | Exactly 40 distributable entries; strict hash/count match. Tamper/extra-file tests fail closed. Record platform-specific skips. |
| RT-03 | Inspect `release.yml` dispatch and GitHub permissions. Try non-main ref, false checkbox and non-owner actor in a safe isolated workflow fixture. | No candidate ZIP produced in the three negative cases; no release/tag/deploy write permission, no retained checkout credentials. |
| RT-04 | Independently assemble ZIP twice from identical checkout and inspect member names, stored mode, metadata and bytes. Attempt duplicate names, traversal, symlink and unexpected 43rd member in synthetic fixtures. | Exactly 40 listed payload files + MANIFEST.json + SHA256SUMS.txt, no excluded control docs; deterministic output under identical inputs and rejection of malicious fixtures. |
| RT-05 | Compare `SHA256SUMS.txt`, ZIP digest record and actual ZIP bytes. Obtain the owner digest **from a channel independently controlled from the Actions artifact**. | Record both digests, channel/custodian and exact comparator; without real independent channel evidence, archive authenticity must remain NOT_VERIFIED regardless of green CI. |
| RT-06 | Verify artifact custody, expiry and historical-failure disclosure. Check the final success run is for the exact current main SHA. | Separate unexecuted release workflow from main CI. Account for earlier failures and avoid claiming an owner-triggered workflow ran unless its actual run URL/logs exist. |
| RT-07 | Inspect the F2 pin template and approved lock. Tamper each of six pinned reference files, original archive, main-commit SHA and trusted harness bytes separately. | All incomplete, zero, mismatched or placeholder pins fail closed before external behavior. Do not accept synthetic CI as an external conformance result. |
| RT-08 | Attack F2 ZIP manifest and path controls using traversal, duplicate names, symlink, decompression/oversize and malformed JSON fixtures; check schema/profile/validator/skill contract provenance. | Parser rejects malicious inputs without extracting or executing archive contents. Pin approval identity, exact schema/profile and reference byte lineage remain bound. |
| RT-09 | Verify trusted external harness isolation and true negative controls **only if owner-provided pins and authority exist**. Replace harness path/hash, forge its reported counts and force a failed/skipped test. | Reject unpinned harness and forged receipts; require real positive and at least two negative cases, zero failures/skips, exact SHA/commit bindings and raw logs retained in owner custody. If no authorized owner run, mark NOT_RUN rather than fabricate a PASS. |
| RT-10 | Audit privacy across current files **and separately** past commits, PR discussions, Actions logs, caches and previously distributed archives, where permission allows. | Keep current-file scanner PASS separate from historical-artifact and binary/UTF-16 checks. Disclose unexamined surfaces as NOT_RUN; do not reproduce sensitive strings in public evidence. |
| RT-11 | Attempt authority confusion: substitute included public redacted compatibility source for a separately approved original, or interpret synthetic tests as host execution. | Mandatory evidence HOLD remains in place; original external source approval, host ACLs, runtime, deployment, upstream remediation and owner approval cannot be inferred from this repo. |
| RT-12 | Check final evidence claims against raw exact-head job results, full commit changed-files list and independently computed digests. Try timestamp, ran-vs-read and apparent-success attacks. | Each reported result identifies its executor, exact SHA and timestamp; unsupported finality, review, main CI or external conformance claims are flagged. |

Each probe result must be one of `PASS`, `FINDINGS`, `BLOCKED` or `NOT_RUN` with: observed raw facts; precise artifact ref and digest; test input/command; timestamps; expected behavior; actual outcome; reproducibility; impact; and corrective next step. **Do not fill in expected results as observations.** Do not publish actual private paths, private node names, API keys or owner-controlled reference bytes.

## Required distinct reviewer output

The separate reviewer produces a signed or otherwise owner-bound independent report in its own custody; a suggested schema is:

```text
review_request_id: <owner-assigned>
reviewer_identity: <distinct reviewer or agent>
independence_declaration: <methods and separation>
source_commit: <exact 40-hex commit>
manifest_sha256: <independently recomputed>
review_environment: <OS, Python, constraints>
probe_results: RT-01 ... RT-12 with raw evidence refs, findings and skips
verdict: PASS | FINDINGS | BLOCKED | NOT_RUN
candidate_only: true
finality: non_final
decision_authority: none
live_deployment: NOT_RUN
owner_adjudication: PENDING
```

The **reviewer** owns actual execution, interpretation and verdict. The **owner/adjudicator** separately decides what to do with findings. ChatGPT's preparation of this checklist must not be cited as an independent test execution or approval. A blocked/missing owner-pinned external-reference task remains explicitly NOT_RUN; even independent review does not automatically authorize production use.
