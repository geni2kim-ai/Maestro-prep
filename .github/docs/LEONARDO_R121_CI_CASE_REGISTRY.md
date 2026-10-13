# R1.21 — nine mandatory offline CI case-registry integrity

Date 2026-10-13. Exact prior R1.20 commit `8b2e04769e5b4024d09ff35e96733b0957cab262`. Draft PR #5, candidate-only. No host/deployment or HUMAN/RedAgent authority.

## Observed CI accounting gap

R1.20 `main_ci.main()` iterated arbitrary `CASES`, reported `total=len(results)` and exited 0 whenever `passed==total`. In a bounded function-level simulation of the source's completion condition, 9/9, 8/8 and **0/0** all yield true, and duplicate replacement of a required step could also yield 9/9. This is a source-derived regression risk, **not a live attack against the operator node**.

## Fix

- Lock all nine mandatory `CASES` entries (name + exact argv + kind) using canonical compact UTF-8 JSON SHA256 `c890a85a663ad2279c9bdaf4f8fcaf71793cf740ede2b62d0541da24b908dab1`. Verify tuple/list/str shapes and exact count before any subprocess runs.
- If the registry is missing, shortened, empty, duplicated, changed in command or kind, return code 2 with `CI_CASE_REGISTRY_MISMATCH`, without running children. Always report `total=9`, never vacuous 0/0 success.
- Retain 9 original child checks and policies; add 3 pinned regression methods testing normal contract, deleted/empty case list, substituted and mutated commands/kinds.
- Adjust reviewed accounting suite `38 -> 41`, exact 41-method names and whole source SHA256 `4e59326682a1a1db305a7b90bf8d62d94d770bbfb017b2f2e04282f0f10b72ca` (candidate-owned, not a cryptographic external signature).
- Product runtime O-Prep, Leonardo router adapter, manifest inventory and Windows node policies unchanged.

## Leonardo / CodeDiff boundaries

Leo R2.30 policy-use source (`leonardo_use_policy.py` blob `2dedbc58ba968da3d10fd783f54f43e762c52763`) treats authority-sensitive multiagent pipeline changes as deep-review candidates; here it is a **policy-guided security scenario**, not a full `route_task` or model execution.
Run GitHub CI six OS/Python environments; expect all nine public gates, 41 accounting tests, 40-file manifest, 20 replay scenarios and pinned CodeDiff v2.5 SHADOW. CodeDiff remains `action_required` and non-authoritative; independent RedAgent/HUMAN, real Win11 standard-user symlink privilege cases and trusted Leonardo local router remain NOT_RUN/HOLD. No new local sandbox package is required for this portable CI-only change.
