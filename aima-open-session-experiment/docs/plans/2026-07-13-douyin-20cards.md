# Douyin 20-Card and 90-Second Video Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce a factual 20-card Douyin carousel and a roughly 90-second vertical H.264 video that combine captured experiment evidence with clearly labelled AI-generated explanatory diagrams.

**Architecture:** Extend the existing PIL card generator with deterministic local charts and AI diagram inputs. Generate the video from the same ordered card set using ffmpeg concat durations, then validate media and Markdown references before saving Douyin drafts.

**Tech Stack:** Python 3, Pillow, matplotlib (if available), ffmpeg/imageio-ffmpeg, JSON metrics, Markdown, Chrome upload flow.

---

### Task 1: Stage AI diagram assets

**Files:**
- Create: `assets/ai-diagrams/ai-01-perception-action.png`
- Create: `assets/ai-diagrams/ai-02-data-pipeline.png`
- Create: `assets/ai-diagrams/ai-03-closed-loop.png`
- Create: `assets/ai-diagrams/ai-04-failure-roadmap.png`

**Step 1:** Copy the four generated PNGs into the repository, preserving the original generated files.

**Step 2:** Verify each image is decodable and record dimensions with `file`/Pillow.

**Step 3:** Commit only the diagram assets and design docs.

### Task 2: Extend the carousel generator

**Files:**
- Modify: `scripts/make_carousel.py`
- Create: `assets/plots/metrics-base-lora.png`
- Create: `assets/plots/episode-distance.png`
- Create: `assets/plots/action-counts.png`

**Step 1:** Add a deterministic card specification for 20 cards, mapping each card to a real screenshot, local chart, or AI diagram.

**Step 2:** Load `eval_result.json` for all numeric overlays; do not hardcode metrics that can drift.

**Step 3:** Render charts and cards at 1080×1440 with a consistent header/footer and a visible “AI 生成示意图” label on AI cards.

**Step 4:** Run the generator and verify exactly 20 JPEGs are produced with non-zero dimensions.

### Task 3: Expand article copy

**Files:**
- Modify: `article/抖音-智元布道师图文稿.md`

**Step 1:** Replace the 8-card section with 20 card scripts, keeping the actual base/LoRA metrics and failure boundaries.

**Step 2:** Add a long-form caption, AI-diagram disclosure, comment prompts, and a 20-card preflight checklist.

**Step 3:** Run a path scan to ensure all referenced assets exist and no sensitive identifiers appear.

### Task 4: Build and validate the 90-second video

**Files:**
- Modify: `scripts/make_media.py`
- Create: `assets/videos/stage1-smoke-retrospective-vertical-90s.mp4`

**Step 1:** Reuse the 20-card order and assign 4–6 second durations, with longer holds for metrics and closing cards.

**Step 2:** Encode at 1080×1920, 30fps, H.264, silent audio track, and faststart.

**Step 3:** Validate duration (85–100 seconds), codec, frame rate, resolution, and decodability with `ffprobe` and a frame extraction.

### Task 5: Run repository checks and prepare drafts

**Files:**
- Update: `run-manifest.json` or the current manifest generator output with new media hashes.

**Step 1:** Run Python compilation/tests and `git diff --check`.

**Step 2:** Hash the 20 cards, AI diagrams, plots, GIF, and MP4; update the manifest.

**Step 3:** Use the controlled Chrome upload flow to replace the image and video drafts, save both as drafts, and stop before final publish.

**Step 4:** Report exact local paths, validation results, and the user-confirmation boundary.
