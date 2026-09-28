# Evidence: v0.1.0 public-redacted hotfix follow-up

- Repository: `geni2kim-ai/Maestro-prep` (**main** only, not a Leonardo-repository change).
- Feedback read first: [feedback_v0.1.0-public-redacted-hotfix.md](../feedback/feedback_v0.1.0-public-redacted-hotfix.md), Git blob `e21208346c34bbeb88a2608d8312d7a222645aff`.
- Source revision tested: [df54d983c8beb69098f03c85589ae4ccce861ba9](https://github.com/geni2kim-ai/Maestro-prep/commit/df54d983c8beb69098f03c85589ae4ccce861ba9), `main`.
- Package version retained: `0.1.0-public-redacted-hotfix` (no promotion of the separate Draft candidate).
- Verification event: 2026-09-28 00:31 UTC, [main push run 36362504113](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36362504113), **completed/success**, all four jobs green.
- Scope: exact Git checkout of this public-redacted profile, synthetic fixtures and repository-local checks. Candidate-only, non-final, no runtime/deployment authority.

## Feedback item 1 — Main-branch CI

**Implemented and executed.** The initial main tree had no workflow, whereas the Draft candidate had its own distinct `candidate-ci.yml` and runner. Added `.github/workflows/candidate-ci.yml` on main with `push: main`, PR-to-main and manual-dispatch triggers, read-only GitHub token permissions, SHA-pinned checkout/setup-python, no persisted checkout credentials and a four-job Python/OS matrix. Added `.github/scripts/main_ci.py` and `.github/scripts/run_public_component_tests.py` specifically for the initial main profile; did not copy the Draft-only integration jobs or advertise their results as main evidence.

The first main attempts identified defects in the *new CI integration* and were retained as historical failures rather than concealed:
- [36362316972](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36362316972): CI minimum incorrectly assumed 35 coordinator tests rather than the frozen main suite's 30; Windows additionally exposed checkout byte differences.
- [36362350738](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36362350738): after correcting the coordinator minimum to 30, Linux passed; Windows still showed checkout-induced pinned-byte mismatches.
- [36362427558](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36362427558): after adding a root `.gitattributes` with `* -text`, the Windows component pin and replay passed, revealing a second portability defect: manifest comparison used platform-dependent `Path` ordering.
- [36362504113](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36362504113): after sorting inventory by explicit POSIX path strings, **Ubuntu/Windows, Python 3.11/3.13: four of four jobs succeeded**. Release inventory, public privacy, included component pin, coordinator tests, included compatibility tests and synthetic replay passed in each job.

The manifest and checksum inventory were regenerated whenever a packaged source file changed. Final frozen inventory remains 40 distributable files. `.gitattributes`, `.github` control material, this evidence Markdown and its precisely named feedback are non-distributable control records; unexpected additional application files still cause a manifest mismatch. The published manifest is an inventory, not an externally signed archive authentication.

## Feedback item 2 — README badge versus main verification

**Reconciled without an unearned badge.** The inspected main README had no CI or release badge, contrary to the feedback's description; those historical claims were not taken as current main evidence. Updated English and Korean READMEs to link the actual main workflow and supported local checks, explicitly distinguishing the original public profile from the unmerged Draft. Deliberately kept the README badge-free rather than linking a Draft run or suggesting a main run passed before it existed. Exact successful main run and SHA are bound above.

## Feedback item 3 — Public planning-reference conformance workflow

**History checked; scope and substitute documented.** Commit `b38f2c786f3699259238c625c4826f66e9dbf74c` does not list a workflow change and its inspected main parent has no `.github/workflows` tree. Available main history therefore does not demonstrate that this commit removed the named public planning-reference conformance job. The distinct Draft workflow is not proof of main conformance and was not silently promoted. [Release CI and reviewer gates](../.github/docs/RELEASE_CI_AND_REVIEW.md) records the finding and defines repository-local manifest, included-component and synthetic planning-contract checks as the **limited offline substitute**. External approved-reference conformance remains **NOT_RUN** pending owner-approved external source bytes, profile/schema/hash pins, a separate negative-control harness and exact-commit receipts.

## Feedback item 4 — Release 0.1 evidence re-execution

**Current-checkout integrity and synthetic regression re-executed; archive authenticity separately bounded.** Historical `RUN_REPORT.json` is preserved as a producer-reported baseline, not re-labelled as a new run. The fresh exact-source main CI run above recorded the following in **each** of its four jobs:

| Check | Ubuntu 3.11 | Ubuntu 3.13 | Windows 3.11 | Windows 3.13 |
| --- | --- | --- | --- | --- |
| Manifest + SHA256SUMS, 40 files | PASS | PASS | PASS | PASS |
| Current-file public privacy scanner | PASS | PASS | PASS | PASS |
| Included redacted compatibility source pin | PASS | PASS | PASS | PASS |
| Coordinator suite | 30 run, 0 skipped, PASS | 30 run, 0 skipped, PASS | 30 run, 0 skipped, PASS | 30 run, 0 skipped, PASS |
| Included compatibility suite | 61 run, 5 skipped, PASS | 61 run, 5 skipped, PASS | 61 run, 6 skipped, PASS | 61 run, 6 skipped, PASS |
| Synthetic architectural replay | 20 matched, PASS | 20 matched, PASS | 20 matched, PASS | 20 matched, PASS |
| CI runner check receipts | 6/6 PASS | 6/6 PASS | 6/6 PASS | 6/6 PASS |

Job IDs for [this exact run](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36362504113): Ubuntu 3.13 `108742330993`; Ubuntu 3.11 `108742331171`; Windows 3.11 `108742331189`; Windows 3.13 `108742331251`. Included-component skips are not silently counted as executed successes. In the Windows suite, one additional POSIX-only file-mode assertion is explicitly marked inapplicable; actual host NTFS ACL validation remains NOT_RUN. Tests with optional dependencies also report their skips; the source was not modified to turn missing optional dependencies into passes.

No immutable, independently SHA-pinned release ZIP was assembled or verified against a separate trusted out-of-band archive digest in this task. **Release archive authenticity: NOT_RUN.** That gate requires building final immutable distributable bytes, publishing their full archive digest through an owner-controlled independent channel, and comparing it against the received archive on an isolated machine. Manifest success proves only the current checkout's claimed distributable bytes are internally consistent.

## Feedback item 5 — Draft PR #1 disposition

**Intentionally segregated; not merged.** [Draft PR #1](https://github.com/geni2kim-ai/Maestro-prep/pull/1), branch `fix/leonardo-connection-v0.2`, remains a distinct candidate with features absent from main. This feedback did not authorize promotion of that wider branch. Before any future merge, require an explicit owner decision, an exact-head branch diff, independent privacy and security review of added code/history, fresh source inventory and exact-head CI receipts. This task changed main's initial public profile only.

## Feedback item 6 — Independent-review and runtime authority

**Boundary preserved and entry criteria recorded.** Automated main CI is not an independent red-team review. Independent reviewer authority is **NOT_GRANTED** and review execution **NOT_RUN**. Qualification requires an owner-appointed separate reviewer, immutable source/manifest and evidence inputs, explicit scope and review identity, and a retained findings/adjudication receipt. External real-host integration additionally requires approved component/provider source pins, isolated owner-generated local receipts, separate host security checks, a rollback plan and explicit authorization. No live router, approved host planning installation, host mutation, deployment, external vendor/reference certification or final adoption occurred.

## Recorded scope and residual gates

- Final tested source revision: `df54d983c8beb69098f03c85589ae4ccce861ba9`; the only intended change in the subsequent evidence-publication commit is this report, expressly excluded from the 40-file release inventory.
- Main CI on that revision: **SUCCESS**, 4/4 platform jobs, each 6/6 repository-local checks.
- Supported statements: frozen checkout hash inventory, current-file privacy scanner, included *public derivative* source pin, synthetic tests/replay.
- Unsupported statements: independent reviewer conclusion; historical Git-object/cache erasure; original external component approval; independent archive authenticity; genuine cross-repository reference conformance; actual host execution or security; runtime authorization, deployment or finality. All remain NOT_RUN, NOT_VERIFIED or NOT_GRANTED as applicable.
