# Maestro-Prep

**Maestro-Prep v0.1** is a public, pre-release skill package that coordinates **Astra-Prep** (planning) and **O-Prep** (evidence-bound checks) through a common Leonardo-oriented entry point.

This is an **offline, candidate-only** implementation. It does **not** include the official Astra-Prep source, a Leonardo router binary, production data, node credentials, or private node logs. The included comparisons and tests are synthetic and are not proof of live-node integration.

## Getting started

See [SKILL.md](SKILL.md) for the skill contract and [README_KO.md](README_KO.md) for the Korean guide.

The complete v0.1 candidate source is available directly in this repository, including the O-Prep component, schemas, synthetic examples, tests, integration contracts, and manifests. Clone this repository to run the offline checks.

From the extracted directory:

```bash
python tools/verify_package.py .
python -m unittest discover -s tests -q
python -m unittest discover -s components/o_prep_v0_3/tests -q
python tools/replay_simulation.py
```

## Integration boundary

The official Astra-Prep version and each node's approved Leonardo router/policy must be independently obtained, verified, and integrated in a private, authorized environment. This package does not automatically install to shared, production, or live nodes, and its output is not an authorization to deploy.

## Privacy

This repository contains generalized implementation, documentation, and synthetic fixtures only. **Do not commit private node codebases, real logs, secrets, credentials, production DBs, or unauthorized evidence bundles.**

Public visibility does not, by itself, grant a software reuse license. No software license is declared in this initial candidate publication.
