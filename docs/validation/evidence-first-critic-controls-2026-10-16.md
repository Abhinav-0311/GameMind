# Critic context and evidence-first experiment — 2026-10-16

Production change: `backend/app/design_agent/nvidia_provider.py` now applies the existing compact critic projection to contract v2, removes exact regenerated quest-check duplicates without dropping authored notes or state/eligibility data, and clarifies coverage, proposal status and field-reference guidance. Provenance still binds the original full artifact.

Two controls were added in `backend/test_independent_critic_boundary.py`; existing prompt assertions were updated in `backend/test_design_contract_v2.py`. Final local selection: 597 passed, five PostgreSQL-fixture cases deselected. Backend-container subset: 108 passed. These are not full-suite or hosted-quality claims.

Six authorized NVIDIA requests were consumed, including a truncation retry, in `gamemind_test_qa_20261016_6e8b20af` / `qa_frostpeak_evidence_20261016_6e8b20af`. The experimental input produced novel lines and the five-ore total but still missed dialogue stages/failures and invented quest-giver restart requirements. It remains QA-only.

The known-bad control received zero raw model findings. The manually authored corrected target control received two false-positive proposal findings. A final candidate critique again returned zero raw findings; application checks kept it blocked. Model critique reliability is not fixed.

All 234 preserved-table fingerprints and environment hashes were unchanged; no approval/export, model changes, installs, commits or pushes occurred. Intermediate API approval checks intermittently failed before final clean runs; no proven cause or fix is claimed for that observation.

Detailed private QA report: README (`<QA_DIR>/qa-frostpeak-evidence-20261016-6e8b20af/README.md`).

Do not advance product readiness based on these results. Next proof must demonstrate useful staged dialogue/quests and correct discrimination between known-bad and corrected drafts.

