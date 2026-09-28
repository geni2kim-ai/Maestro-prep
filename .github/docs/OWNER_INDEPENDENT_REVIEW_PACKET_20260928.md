# Owner nomination and immutable-source reviewer handoff

**Status:** `REVIEW_PACKAGE_PREPARED`; reviewer `NOT_ASSIGNED`; independent execution and verdict `NOT_RUN`. Prepared for the owner of `geni2kim-ai/Maestro-prep`. ChatGPT compiled this handoff and previously authored the F3 checklist and R1 same-lineage source review, so this document is **not** an independent assessment or a claim that a separate person/agent has accepted the assignment.

## 1. Owner nomination required

Owner (Genie Kim): please **name a different human reviewer or separately appointed agent**, state its actual organizational/context separation from the checklist author and prior R1 reviewer, and send the *same immutable input bundle* to that reviewer through a controlled channel. Record at minimum `review_request_id`, `reviewer_identity`, `reviewer_type`, `independence_declaration`, `review_scope`, `approved_source_commit`, `approved_methods`, `handoff_timestamp_utc`, `reviewer_ack`, and `owner_adjudicator`.

A route called “separate agent” is not automatically independent. A reviewer with the same context, authorship or stake must declare that limitation. The owner—not this packet—decides whether the required independence standard is met. No reviewer was nominated, contacted or scheduled here.

## 2. Bounded review scope and authority

- **In scope:** current `Maestro-prep` source and CI/control workflows; 40-file public manifest, checksums, deterministic candidate ZIP, local current-file privacy scanner, synthetic external-pin gate, test receipts and the F3 RT-01–RT-12 checklist. The earlier ChatGPT R1 review is *claimed author evidence to scrutinize*, not an independent acceptance.
- **Out of scope by default:** production/runtime/host mutation, other users' accounts, releases or external systems, private Astra installations and unapproved reference bytes, older caches and distributed copies outside the repository, and any automatic merge, dispatch, promotion or deployment. If a later owner-approved review expands these boundaries, it requires a **new explicit scoped assignment**, not implied consent from this packet.
- All execution must use the reviewer’s own isolated synthetic environment and only approved repo inputs. Read-only inspection is preferred; when synthetic tests create files, use temporary controlled directories. Preserve a pristine independent source copy and record test tool versions and platform-specific skips.
- Every result is `candidate_only=true`, `finality=non_final`, `decision_authority=none`. The reviewer does not approve its own results for deployment.

## 3. Freeze the inputs before work

**Prepared source snapshot** (after public pin proposal, before adding this reviewer-packet document): [`3796e8e29fe518ccd41a063fc49c6e86ac3930a0`](https://github.com/geni2kim-ai/Maestro-prep/tree/3796e8e29fe518ccd41a063fc49c6e86ac3930a0). The owner can nominate this exact commit or explicitly substitute another **full 40-character commit** and regenerate all accompanying bindings. A moving `main` pointer is never an immutable input.

| Input | Immutable binding / source |
| --- | --- |
| `MANIFEST.json` | Git blob `d92492b93d1feb164f5e37b307345c0e709a48b0`; UTF-8 6,962 bytes; raw SHA-256 `2035a8ca8277ff5d741dfc5ef8c0a0949910f7946b7360265aebb2f893e6500a`; exactly 40 distribution entries. Reviewer must recompute. |
| `SHA256SUMS.txt` | Git blob `4f064b4eb746ad6089a079cef525169e749e1ea0`; 40 checksum lines. Reconcile each ordered line with the 40 manifest entries and current checkout bytes. |
| F3 checklist | [`.github/docs/RED_TEAM_CHECKLIST_DRAFT.md`](RED_TEAM_CHECKLIST_DRAFT.md), Git blob `23bddffc92872b61da929905dfd9acfafeb5564f`, RT-01–RT-12. |
| Prior **same-lineage** findings | [`evidence_v0.1.0-public-redacted-hotfix_redteam1.md`](../../evidence/evidence_v0.1.0-public-redacted-hotfix_redteam1.md), Git blob `2299411560866080170573a3d0f8afe23e444e6a`; reviewer must not promote its self-reported results into separate reviewer evidence. |
| Owner’s unapproved Astra pin proposal | [`ASTRA_PIN_PROPOSAL_20260928.md`](ASTRA_PIN_PROPOSAL_20260928.md), Git blob `36785d74d4ff56b3d8feb5a4544849b010d2aeff`. This is **candidate-only**; no owner-provided external reference or harness. |
| Exact prepared-source CI receipt | [main push run `36376386397`](https://github.com/geni2kim-ai/Maestro-prep/actions/runs/36376386397), linked to `3796e8e29fe518ccd41a063fc49c6e86ac3930a0`; `completed/success`. Owner must supply and reviewer must compare exact job details, rather than inheriting the status from this packet. |

The owner/reviewer should record *raw* archived snapshot SHA-256 and any independently supplied ZIP digest **only after those exact bytes exist**. Neither the prior self-test ZIP nor a guessed path is evidence of an owner-released immutable archive. The newly published reviewer packet and subsequent evidence report will create later documentation-only Git commits; their entire Git trees differ from the prepared snapshot even if the 40-file distributable payload remains unchanged. If the owner chooses the later head, the reviewer must rebind `approved_source_commit` and verify its exact-head CI independently.

## 4. Review method and acceptance criteria

Use all 12 probes in the checked-in F3 checklist and document each as `PASS`, `FINDINGS`, `BLOCKED` or `NOT_RUN`. Provide the reviewer’s **own** evidence, rather than copying expected conclusions:

- **RT-01, RT-02, RT-06, RT-12:** source/commit provenance; fresh per-file and aggregate hashing; distinguish actual test run from read-only source or earlier author report; bind timestamps, runner, exact head SHA, platform-dependent skipped tests and provenance of artifacts.
- **RT-03–RT-05:** static owner-actor/main/manual checkbox/permission checks and isolated synthetic ZIP boundary checks. Distinguish the 40-file checkout inventory and a temporary 42-entry test ZIP from an actual manually produced Owner release; compare the latter’s digest only when the Owner independently supplies it.
- **RT-07–RT-09:** verify strict local external-pin contract and synthetic input handling; separately mark real owner-provisioned Astra reference pins, accepted harness and approved offline run as `NOT_RUN` without those exact bytes and explicit permission. Do not fetch, install or invoke an unapproved external service.
- **RT-10:** current-tree pattern scanner and synthetic non-UTF-8/UTF-16 handling. Historical Git blobs, PR discussion, external artifacts and caches require distinct permissions and receipts; do not mark them `PASS` merely from a clean current-tree scan.
- **RT-11:** separate public redacted compatibility, public Astra source **candidate**, original owner-approved installation, Owner release authority and runtime/deploy gates. A valid synthetic test is not external approval.

**Minimum reviewer report:** immutable request ID and target commit, reviewer identity/separation, acquisition timestamp/channel and complete input digest inventory, test/platform/tools and exact commands, raw source/action refs, each RT-01–RT-12 finding and skipped-scope rationale, severity/rationale for findings, reproducibility/negative controls, `PASS|FINDINGS|BLOCKED|NOT_RUN` overall verdict, `candidate_only=true`, `finality=non_final`, `decision_authority=none`, `owner_adjudication=PENDING`. Any claimed independent execution must have its own raw receipt and not be inferred from the previous ChatGPT R1.

**Owner adjudication:** acknowledge receiving the distinct reviewer report; independently assess required source fixes and whether a fresh review round is needed. Even a fully documented `PASS` here does **not** grant production deployment, external-reference approval, a release signature or finality.

## 5. Owner assignment response requested

The owner should fill and retain this short private assignment block, without embedding private reference bytes or access tokens in GitHub:

```text
review_request_id: OWNER_TO_FILL
reviewer_identity_and_type: OWNER_TO_NOMINATE
independence_declaration_and_prior_involvement: OWNER_TO_VERIFY
approved_source_commit: 3796e8e29fe518ccd41a063fc49c6e86ac3930a0 OR REBOUND_EXACT_COMMIT
scope: MAESTRO_PREP_SOURCE_AND_WORKFLOWS_ONLY
test_permissions: READ_ONLY_PLUS_ISOLATED_SYNTHETIC_FIXTURES
handoff_source_sha256_and_channel: NOT_YET_PROVIDED
reviewer_ack_and_utc_time: NOT_YET_RECEIVED
review_execution: NOT_RUN
owner_adjudication: PENDING
```

Until the named independent reviewer acknowledges the exact frozen inputs and performs the separate procedure, `reviewer_status=NOT_ASSIGNED`, `independent_review=NOT_RUN`, `owner_acceptance=PENDING`.
