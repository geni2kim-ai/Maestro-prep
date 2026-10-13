# R1.24.1 — Windows test fixture escape correction

Date 2026-10-13. Direct parent R1.24 commit `f5317c26acc541a9298a4a28788d05428bf3b9af`.

GitHub Actions Run #103 reported failure in the Windows 3.12 job, specifically `test_zip_member_ambiguous_alias_is_rejected_before_manifest`. Its test fixture wrote a literal backslash followed by `n` instead of a newline character. On Windows the zipfile module converts backslash separators to forward slashes, so a different path was tested and the failure happened downstream as `manifest_entry_count_mismatch`. This is a genuine portability error in the **new regression test**, not proof the new O-Prep production path validator failed.

Fix only those synthetic test strings to concatenate `chr(10)` for an actual control character, independent of source escaping and platform path separators. Retain all O-Prep implementation code and `SOURCE_PIN.json` unchanged. Update test file entry in the 40-file `MANIFEST.json` and `SHA256SUMS.txt`. Require fresh GitHub Windows/Ubuntu Python 3.11/3.12/3.13, nine offline checks, CodeDiff v2.5 SHADOW and tracked-source snapshot before considering candidate CI green. SHADOW remains nonauthoritative, HUMAN and independent RedAgent remain NOT_RUN and deploy/merge blocked.
