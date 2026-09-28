# F2 owner pin request — external reference conformance (DRAFT)

**Current gate: NOT_RUN.** No approved external-source bytes or owner permission were supplied by this feedback. The current public synthetic checks and included redacted compatibility component **do not** satisfy external reference conformance.

The owner must provide these materials *only in a controlled, isolated runner/private handoff*, not through public issues, PR comments, workflow variables with sensitive contents, or this repository. Pin **raw exact bytes**, not filenames, supplier labels or inferred versions:

1. Exact approved `reference_archive.zip` and its full 64-character lowercase SHA-256; source identity, original supplier/version, permitted test-only use, and provenance.
2. Exact `profile.json` content with profile/version/accepted operations and its byte SHA-256.
3. Exact `schema.json` content, schema identifier/version and byte SHA-256.
4. Exact approved `validator.py` source byte SHA-256 and invocation contract (this gate hashes it but does not execute it automatically).
5. Exact `SKILL.md` integration contract byte SHA-256 for the separately approved external installation.
6. Exact `bundle_manifest.json` and its byte SHA-256. Manifest schema: `OWNER_APPROVED_REFERENCE_BUNDLE_V1`, with `files: [{path, bytes, sha256}]` describing **every** regular file inside the approved ZIP, with relative POSIX paths, no duplicates or symlinks. The gate verifies membership and raw bytes without extraction.
7. A trusted, independently owner-selected `owner_harness.py` outside this repository and outside the approved reference root, its exact SHA-256, and a written contract that it tests **at least one positive and two negative controls** (e.g. corrupted profile/schema, changed source bytes, malformed input) against actual pinned reference behavior, without network, mutation, deployment or live provider use.
8. Exact 40-hex main commit SHA against which those pins are approved, unique owner approval identifier (not the placeholder), scope `OFFLINE_REFERENCE_CONFORMANCE_ONLY`, and explicit authorization for the self-hosted offline conformance attempt.

Write the private pin file using [template](EXTERNAL_REFERENCE_PIN_TEMPLATE.json), replacing **every** placeholder. Do not commit the filled file. Set only three non-sensitive absolute *paths* via GitHub repository variables `MAESTRO_APPROVED_REFERENCE_ROOT`, `MAESTRO_OWNER_PIN_FILE`, and `MAESTRO_TRUSTED_HARNESS`. Provision a controlled self-hosted runner with the three labels `self-hosted`, `maestro-owner-approved`, `isolated`, local Python 3.11+ and blocked outbound network. Restrict who can dispatch this workflow. Owner must manually dispatch it on the **exact approved main commit** with the checkbox enabled.

The harness contract receives `--reference-root`, `--pin`, `--receipt-output`, and must write JSON with **exact fields**: `schema=MAESTRO_OWNER_HARNESS_RECEIPT_V1`, `status=PASS`, `source_commit`, `pin_sha256`, `reference_archive_sha256`, `cases={positive,negative,failed,skipped}`, `scope=OFFLINE_APPROVED_REFERENCE_ONLY`, `authority=none`. Values must be bound to the exact validated inputs, `positive>=1`, `negative>=2`, `failed=skipped=0`. The gate checks the receipt's shape, but **cannot independently establish harness trust**; approval and independent adversarial review remain separate. The workflow uploads only a **candidate metadata receipt**, never owner source bytes or operational secrets.

The `DRAFT owner-gated external reference conformance` workflow is **not enabled for ordinary GitHub-hosted CI** and cannot pass without the owner-provisioned pin file, source files, trusted external harness and isolated runner. We have not dispatched it. Until owner material, owner run approval, and independent review exist, external conformance remains **NOT_RUN**, review **NOT_RUN**, authority **NOT_GRANTED**.
