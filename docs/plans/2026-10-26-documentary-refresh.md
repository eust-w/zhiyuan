# Documentary Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a clearer public README and a truthful, editable documentary sample before producing and publishing platform-specific full versions.

**Architecture:** Preserve the model adapter and canonical experiment evidence. Use an isolated media restoration directory and a new `documentary/` Remotion project, with explicit source categories and fact assertions. Voice, archive review, visual preview, and platform publication are separate acceptance gates.

**Tech Stack:** Markdown, Python standard-library assertions, Remotion/React/TypeScript, Node test runner, FFmpeg/ffprobe, Gitleaks, hash-locked existing audit environment.

---

The user approved the direction and execution in this chat. Use the existing isolated checkout on `codex/aima-vln-experiment`, not the deleted original workspace. Unavailable superpowers helper skills are replaced by explicit ownership, test-first changes, independent review and remote verification. No GPU or paid generation is started without new authority.

## Task 1: Public README

**Modify:** `README.md` only.

1. Retain canonical metrics and licensing caveats; replace the report-like opening with concise positioning and three reading routes.
2. Add an evidence gallery and distinguish historical experiment results from current 132-test CPU verification.
3. Describe contribution challenges by acceptance criteria.
4. Check local links and metric values, run the documented standard-library test command, review the diff and secret scan.

## Task 2: Archive restoration and safety

**Location:** isolated temporary recovery directory, never tracked in Git.

1. Read Release metadata, download the 17 existing split assets and verify published SHA-256 values.
2. Inspect archive members without execution; reject unsafe paths/links and enforce a storage budget.
3. Scan text members for secrets and identifying data, report only redacted findings.
4. Extract needed media selectively; verify hashes, ffprobe properties and full decoding. Inventory source categories and missing continuous operation recordings.

## Task 3: Storyboard and factual contract

**Create:** `documentary/content/sample.json`, `documentary/content/narration.md`, `documentary/tests/contract.test.mjs`, `documentary/scripts/facts.mjs`.

1. Write failing tests for exact historical facts, truthful source labels, unique narration, supported source paths and a 60–90 second timeline.
2. Implement a canonical-JSON fact reader and a short shot manifest; do not duplicate metric constants without assertions.
3. Draft natural Chinese narration with source evidence per shot, no course discussion or unverified program promises.
4. Pass tests before implementing the composition. Track narration as pending until an actual chosen voice has been auditioned.

## Task 4: Editable visual preview

**Create:** `documentary/` scaffold, source compositions, package lock and local media ignore rules.

1. Scaffold and install the official Remotion blank template; open Studio before building the composition.
2. Use dedicated editable scene nodes, deterministic frame-based animation, generous safe areas and local source media.
3. Use genuine data/log replay only where it matches narration; never relabel it as desktop footage or loop to fill duration.
4. Verify typecheck, tests, dependency audit, preview loading and sampled frames. If voice is unavailable, label the deliverable visual-only and do not claim the sample is fully finished.

## Task 5: Review, push and later publication

1. Review README and preview for factual accuracy, source labels, legibility and privacy.
2. Run relevant audits before commits; exclude restored archives, raw media, credentials, node_modules and generated long videos.
3. Push reviewed changes to the configured GitHub branch and verify the remote commit and CI.
4. After voice/style approval, build full platform versions. Save online drafts only after verified login; final submission remains user-confirmed.

## Acceptance boundaries

Repository visibility, local edits, pushed commits, editable visual preview, synthesized audio, complete video, online draft, submitted content, and public URL are separate states. Report each accurately. Never present historical media acceptance or CPU model tests as proof of the new documentary or GPU navigation behavior.
