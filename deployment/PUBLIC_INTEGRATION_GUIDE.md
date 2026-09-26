# Public integration guidance (non-authorizing)

1. Obtain a candidate ZIP and its SHA-256 through separate owner-controlled channels; verify package members and source pins without extracting untrusted node evidence.
2. Record effective local router, planning component and evidence component hashes in local-only configuration. Do not publish host paths, raw policy, private skill names or original evidence archives.
3. Audit third-party ZIP member integrity with the generic public archive tool. Validate original provider semantics using an independently authorized private adapter.
4. Run isolated, offline checks. Report synthetic/bytes-only successes independently from approved host execution and human/independent review.
5. On any missing pin, noncanonical source or policy mismatch, HOLD without installing or changing an existing component. Rehearse rollback and obtain owner approval separately before any actual deployment.
