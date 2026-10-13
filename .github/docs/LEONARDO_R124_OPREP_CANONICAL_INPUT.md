# R1.24 — O-Prep canonical evidence paths and JSON shape gate

Date: 2026-10-13. Base commit R1.23 `8bab35ec7079516e6a8d9941ca3089b2d0e127d0`; candidate-only Draft PR #5.

## Leonardo policy-guided bounded analysis (not a live Leonardo run)

O-Prep ZIP name acceptance used `PurePosixPath` plus only checks for '.' and '..'. Path `evidence//alias.dat` was valid according to its source predicate while the standard path parser normalizes it to `evidence/alias.dat`. ZIP names containing ':' were also accepted, even though Windows can interpret the separator as an NTFS alternate data stream. Local `evidence_bindings._safe_local_file` similarly allowed ':' in intermediate receipt path segments; Maestro coordinator already rejects this class in its own independent file reader. These inconsistencies could lead to ambiguous file identity across producer/consumer platforms, not confirmed host exploitation.

The archive parser required certain JSON files but did not enforce dict/list shape for `snapshot`, `router`, `receipts`, `gates`, `evidence_ledger` before use. A nested array or non-dict could trigger native Python `AttributeError` instead of the explicit fail-closed O-Prep contract. In the CLI such errors could bypass the fixed error response and emit a traceback.

## Targeted changes

- ZIP members must have canonical, nonempty slash-delimited path components, no trailing space/dot, no colon, and no ASCII control characters. Symlink, traversal, absolute-path and count/size checks remain.
- Local receipt references reject the same colon/control-character ambiguity *before filesystem access*.
- Validate top-level JSON evidence document kinds and nested expected `test_suites`, `gates`, `claims`, `queue_status_disk`, `installed_router` containers before dereferencing.
- Four regression methods exercise malicious ZIP names, local ADS paths, malformed required document roots and malformed nested documents.
- Preserve unchanged provenance semantics. New bytes require refreshed `SOURCE_PIN.json`, `MANIFEST.json` (40 entries) and `SHA256SUMS.txt`; no deployed O-Prep host original, agent approval or production mutation.
- Verify on GitHub Ubuntu/Windows Python 3.11/3.12/3.13 plus CodeDiff v2.5 SHADOW and complete-source bundle. SHADOW has no approval authority; independent Leonardo full route_task, RedAgent, HUMAN, real Windows standard-user link testing remain unverified/HOLD. CI-only portability tests do not require a new local-node package.
