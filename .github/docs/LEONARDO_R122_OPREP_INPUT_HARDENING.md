# R1.22 — Leonardo-guided O-Prep public derivative malformed input hardening

Date 2026-10-13. Exact base R1.21 `6ef049783ae583b67d3971484eb6e8686465807c`, Draft PR #5, candidate-only. **Public O-Prep derivative in this repository was deliberately changed** at the user's request; it must not be conflated with any separately host-approved original O-Prep installation. This revision keeps the existing public interface version `0.3.0-prep` but changes candidate source hashes, and these must be freshly reviewed by an independent human before approval.

## Defect analysis / bounded simulation

Direct reading of pinned O-Prep source showed its enumerated status fields were looked up in a `set` without checking `str` first: JSON arrays/objects triggered Python `TypeError: unhashable type` instead of a documented `OPrepError`. Python `bool` is a subclass of `int`: the prior router exit-code equality accepted `True` as numeric exit 1 and `False` as numeric exit 0. Both input classes are producer-controlled, although the bound Maestro coordinator already fails closed on unhandled O-Prep exceptions. This change makes the *component's own* contract and error provenance deterministic.

Both O-Prep JSON readers did not catch CPython `RecursionError` for excessively deep nested input; a local CPython 3.13 standalone recursion stress case reproduced that exception. The O-Prep CLI printed `str(OSError)` and could therefore reveal absolute private host paths in diagnostic stderr on file errors; a disposable path reproduction demonstrated this Python behavior.

These are code-based reproduction and bounded CPython exercises, **not** a full real Leonardo router or local agent simulation. Leonardo R2.30 policy-use source guides stricter review for authority-sensitive multiagent changes.

## Candidate-only corrections

- Validate router/review/delivery enum fields as exact strings before membership checks; reject malformed arrays, objects and null as `OPrepError`.
- Use *exact int* for expected router exit codes; boolean 0/1 aliases no longer accepted.
- Both JSON readers normalize depth-exhaustion / overflow into their respective safe `OPrepError` / `BindingError`.
- CLI emits fixed non-path-bearing `OPREP_HOLD` reasons for file/JSON/type errors and bounded machine-oriented contract error codes only.
- Four targeted adversarial regressions added to existing public v0.3 test suite: malformed enum inputs, boolean exit codes, deep JSON rejection, CLI path redaction.
- Updated source byte pins `SOURCE_PIN.json`, 40-file `MANIFEST.json` and `SHA256SUMS.txt` for modified derivative files; retain pin and inventory validation, O-Prep fail-closed and nonfinal semantics.

## Acceptance and unresolved gates

Run candidate 6-platform GitHub CI (Ubuntu/Windows Python 3.11/3.12/3.13), 40-file manifest, public O-Prep regression, strict mypy, synthetic replay and CodeDiff v2.5 SHADOW on exact HEAD. Explicitly check that no source-pin/hash mismatch occurred and runtime never acquired host authority. O-Prep remains an offline verification gate (component), not a trusted host approval. Windows real symlink privilege tests remain HOLD when unavailable, independent RedAgent/HUMAN and full Leonardo route_task NOT_RUN. This change does not justify merge or deploy.
