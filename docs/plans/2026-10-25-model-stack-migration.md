# Scoped Model Stack Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the existing Qwen + SigLIP + single-device BF16/LoRA path to maintained dependencies, with reproducible local verification and no paid GPU use.

**Architecture:** Keep the pinned StreamVLN source and apply a deterministic, reviewed compatibility overlay before importing it. Keep GenieSim HTTP interfaces, dataset semantics, action IDs, evaluation seeds, and success radius unchanged. Separate CPU model verification from unperformed CUDA and real-checkpoint acceptance.

**Tech Stack:** Python 3.12, current audited PyTorch/torchvision, Transformers 5, PEFT, Accelerate, safetensors; unittest, pip-audit, hash-locked requirements.

---

## Approved scope and authority

The user approved the limited model-stack migration on 2026-10-25 and explicitly declined GPU startup. No instance startup, GPU rental, remote driver change, weight redistribution, or paid validation is authorized in this run. Existing model results remain historical evidence. The deleted original workspace is not restored; work uses an isolated temporary clone.

The available `writing-plans`, `executing-plans`, TDD and verification skills guide delivery. Their `superpowers:*` helper skills are unavailable; equivalent isolated-checkout, task ownership, test-first and independent-review steps are used here. The user has already selected execution in this session.

## Task 1: Dependency profile and local environment

**Files:** create `requirements/model.in`, platform-specific hash locks, `security/model-stack-migration-2026-10-25.md`, audit evidence under `security/evidence/`.

1. Resolve an explicit minimal Qwen/SigLIP/LoRA profile for Python 3.12. Do not install broad upstream extras.
2. Generate full hash locks for local CPU verification and Linux CPU CI. Keep CUDA install choices separate and unverified.
3. Install in an isolated `.venv-model`; run `uv pip check` and strict pip-audit for every resolved distribution.
4. Preserve the historical vulnerable dependency snapshots; do not ignore advisories or claim removed features were migrated.

## Task 2: Pinned upstream compatibility overlay

**Files:** create `aima-open-session-experiment/adapter/streamvln_compat.py`, its patch assets, and `tests/test_streamvln_compat.py`.

1. Add failing tests for unsupported revision/content, idempotence and fail-before-write behavior.
2. Implement a checked, hash-recorded overlay restricted to the fixed upstream revision.
3. Migrate tokenizer output handling, SigLIP config/loading, generation cache preparation, and the existing supervised Trainer contracts.
4. Isolate unused vision/resampler/DPO/DeepSpeed branches; reject unsupported training modes explicitly.
5. Re-run the focused tests and record original and resulting source hashes.

## Task 3: Existing entrypoints and safety boundaries

**Files:** modify `adapter/stage2_preflight.py`, `adapter/model_closed_loop_eval.py`, `adapter/reload_adapter.py`; corresponding tests.

1. Write failing regression tests for Transformers 5 token IDs and compatibility activation before upstream imports.
2. Use the shared overlay from all three entrypoints. Preserve offline/local-safetensors validation before loading any external code.
3. Retain action parsing, reset behavior, vocabulary alignment, model-generated trajectories, and unchanged historical results.
4. Run the existing 96 CPU regressions plus the new focused tests.

## Task 4: Real local tiny-model integration

**Files:** create a dedicated model integration test module and reusable local verification entrypoint if needed.

1. Add tests that instantiate real tiny Qwen and SigLIP configurations with the actual patched StreamVLN classes, without downloading weights.
2. Check multimodal forward/backward, meaningful labels, finite loss/gradients, model-generated tokens, history/cache reset, and tokenizer behavior.
3. Save LoRA using safetensors and reload it in a fresh process; compare parameters and deterministic outputs.
4. Test supported Trainer signatures and save behavior, not just a mock or a no-save configuration.
5. Use real dependency behavior, not fake success fallbacks. Failures block the corresponding local acceptance claim.

## Task 5: CI, documentation, review and delivery

**Files:** modify `.github/workflows/dependency-audit.yml`, `SECURITY.md`, `README.md`, adapter documentation, `THIRD_PARTY_NOTICES.md` as required.

1. Add a separately named CPU model migration gate: hash installation, dependency consistency, audit, pinned overlay and tiny-model integration.
2. Document supported and intentionally excluded paths, installation commands, original-source license boundaries and CUDA/real-checkpoint limitations.
3. Run syntax checks, focused/full applicable tests, audit, secret scan, and `git diff --check`; request independent review.
4. Commit with Conventional Commits and push only reviewed, locally verified changes to the configured GitHub branch. Verify remote commit and CI result.
5. Report local acceptance separately from unperformed GPU verification. No production/GPU certification claim.

## Completion gates

- Full installed local model dependency graph resolves, passes consistency checks and has no reported known advisories in the chosen audit source at audit time.
- Pinned overlay is reproducible, idempotent and rejects unknown modified source before partial writes.
- Real tiny-model training, generation and fresh-process adapter round-trip pass on CPU.
- Existing applicable CPU regressions pass; private media fixtures remain outside this gate.
- CUDA, real checkpoint, actual dataset and GenieSim model loop remain explicitly **not revalidated**.

## Local implementation evidence

The migration adds complete 44-package macOS ARM64 and Linux CPU locks and a checked upstream overlay. Independent review found and corrected both legacy flat-Qwen configuration dispatch and dropped embedded vision weights. The latter changes a historical loading behavior; old navigation results are not new-stack equivalence evidence. Local acceptance comprises 106 existing/entrypoint CPU regressions, 9 source-guard tests and 15 real tiny-model tests, including the original training CLI and fresh-process adapter reload. See `security/model-stack-migration-2026-10-25.md` and its machine-readable evidence for the commands, hashes, audit scope and remaining GPU gate.
