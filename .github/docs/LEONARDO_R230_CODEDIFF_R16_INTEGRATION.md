# Maestro-prep R1.6 Leonardo R2.30 + CodeDiff v2.5 SHADOW integration

## Sources & promotion boundary
- Leonardo private main: \`a4e0bc631d1033e8ba25a0a3e7b1457ca3d6a0d7\`, stable R3 route-form contract.
- Leonardo latest examined R2.30 candidate branch: \`candidate/leonardo-r230-excluded-import-guard-20261012\` at \`80bb6891e772feb506a79dfe2c3beac2b5ae1dcc\`. Draft PR #15 reported failing CI (8 checks) when inspected. This branch is **quarantined**, not vendored into the compulsory O-Prep runtime, and not trusted to authorize candidate advancement. Recheck if it becomes green.
- PR-with-codediff-finder v2.5 \`main\` at \`69a49faa35b56d48e9e3067e5f484b443735df67\`; upstream policy_engine and exactly three policy files retained byte-for-byte at their Git blob SHA in \`.github/review_tools/\`.
- Source pins are in \`.github/review_tools/EXTERNAL_SOURCE_PINS.json\`. Pins to upstream Git objects prove source correspondence, not independent review trust.

## What actually runs
\`.github/scripts/codediff_shadow.py\` runs the **unmodified official v2.5 policy_engine** against a real git base→candidate changed-path inventory, plus a *strict overlay* for Maestro security, provider, protected and governance files. It calls the official \`classify_paths\`, \`derive_risk\`, and \`derive_required_level\`. A dedicated nonprivileged PR GitHub Actions job executes the code and saves metadata-only SHADOW report. Standalone unit tests validate pins, dangerous path classes, rename tracking and the prohibition on Leonardo promotion.

No official TextDiff trusted sensor, L1/L2 review worker, independent Adversarial reviewer, RedAgent or HUMAN review is run. The sensor is \`DEGRADED_GIT_INVENTORY\`, \`trusted_for_gate=false\`, \`gate_conclusion=action_required\`. **The action job succeeding means the SHADOW calculation ran, not that the PR is approved.** R2.30 is selected for compatibility tracking, not executed.

## Local run
From an intact Git checkout with the base commit and candidate head available, after installing PyYAML 6.0.3:

\`\`\`bash
python -I .github/scripts/codediff_shadow.py --repo . --base <BASE40> --head <HEAD40> --out /tmp/maestro-codediff-shadow.json
python -I -m unittest discover -s .github/scripts -p test_codediff_shadow.py -q
\`\`\`

Use separate, fresh output directory. The report intentionally omits diff bodies and secrets. OS-level network sandbox, immutable stable review runner, GitHub required check enforcement, independent review and real Leonardo execution are **NOT_RUN**. Keep PR Draft. Upgrade neither the O-Prep gate nor any approval authority without source, CI and independent-adjudication evidence.
