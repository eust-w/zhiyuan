# GenieSim × StreamVLN Navigation Challenge Video Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Produce one evidence-driven, 10–12 minute Chinese tutorial video that shows the real GenieSim × StreamVLN baseline workflow, data structure, LoRA training, paired Base/LoRA trajectories, measured results, and credible innovation challenges without discussing any course relationship.

**Architecture:** Add an isolated `challenge-video` content pipeline instead of changing the existing four-episode renderer. A typed JSON storyboard is built from repository evidence, a public-text contract prevents forbidden or sensitive wording, sectional TTS produces a natural deep male voice track, and an FFmpeg renderer creates the 1920×1080 master. A separate verifier treats `eval_result.json` and `stage2_result_v2.json` as authoritative sources and blocks delivery unless media, metrics, pairing, wording, and audio checks all pass.

**Tech Stack:** Python 3.11 standard library, Pillow, FFmpeg/ffprobe, Edge TTS, `unittest`, JSON, SRT, H.264/AAC.

---

## Working Rules

- Work in `/Users/longtaowu/workspace/zhiyuan/aima-open-session-experiment`.
- Keep the existing branch `codex/aima-vln-experiment`.
- Do not edit `/root/genie_sim` or the GenieSim adapter API.
- Do not touch, stage, or commit the user's moved `assets/series/智元实验*` files, `.DS_Store` files, or deletions under `assets/series/final-long/`.
- Stage only explicit paths; never run `git add .`.
- Large generated MP4, MP3, WAV, and intermediate render files remain Git-ignored.
- Public outputs include the title, description, narration, SRT, overlay text, cover text, pinned comment, and video frames. They must not contain:
  - `课程`
  - `PDF`
  - `指南`
  - `私有包`
  - `原样复现`
  - `等价适配`
  - `非官方适配`
- Public author copy must not contain email addresses, IP addresses, instance IDs, SSH details, credentials, absolute local paths, or remote Linux paths.
- The neutral public framing is:

  > 在 GenieSim 中搭建 StreamVLN 具身导航 baseline，完成数据采集、LoRA 训练和闭环评测，并探索进一步创新方向。

- Claims about certificates and additional resources must use conditional wording:

  > 完成 baseline 并通过实际验收后，可按活动规则申请智元认证证书；创新成果的算力、技术辅导或展示资源，以主办方实际审核和通知为准。

## Deliverable Layout

```text
content/challenge-video/
├── challenge-manifest.json
├── challenge-source.json
├── narration-sections.json
├── voice-config.json
├── voice-metadata.json
├── publish-package.json
├── publishing-state.json
└── acceptance.json
assets/challenge-video/
├── audio/                         # generated audio, ignored
├── auditions/                     # generated voice samples, ignored
├── final/
│   ├── geniesim-streamvln-challenge.mp4  # ignored
│   ├── geniesim-streamvln-challenge.srt
│   └── geniesim-streamvln-challenge-media-manifest.json
├── preview/
│   ├── style-sample-60s.mp4        # ignored
│   └── contact-sheet.jpg
└── work/                           # generated intermediates, ignored
article/
└── challenge-video-publish-package.md
scripts/
├── challenge_video_contract.py
├── build_challenge_video_manifest.py
├── synthesize_challenge_voice.py
├── build_challenge_video.py
└── verify_challenge_video.py
tests/
├── test_challenge_video_contract.py
├── test_challenge_video_manifest.py
├── test_challenge_voice.py
├── test_challenge_video_renderer.py
└── test_challenge_video_verification.py
```

## Authoritative Evidence

The implementation must read facts from these files rather than duplicating them as editable constants:

| Fact | Authoritative file |
|---|---|
| Base/LoRA held-out metrics and per-episode results | `experiments/exp02-equivalent-v3/eval_result.json` |
| LoRA update count, first/last loss, finite checks, peak memory, reload | `experiments/exp02-equivalent-v3/stage2_result_v2.json` |
| Dataset count and validation | `experiments/exp02-equivalent-v3/dataset-validation.json` |
| Runtime scene, robot, camera and Stage 0 evidence | `experiments/exp02-equivalent-v3/stage0-health.json`, `stage0-keyboard.json`, `stage0-forward-check.json` |
| Evidence hashes | `experiments/exp02-equivalent-v3/run-manifest.json` |
| Training log view | `experiments/exp02-equivalent-v3/logs/stage2-train.stdout.log` |
| Real replay footage | `assets/series/recapture/raw/*.mp4` and `assets/series/recapture/canonical/*.mp4` |

The expected public metric snapshot is:

```json
{
  "gpu": "NVIDIA L40 48GB",
  "train_episodes": 50,
  "heldout_episodes": 10,
  "lora_updates": 59,
  "loss_first": 0.4167,
  "loss_last": 0.0823,
  "peak_gpu_memory_gib": 27.19,
  "base": {
    "success_0_5": 0,
    "success_3": 2,
    "mean_spl_0_5": 0.0,
    "mean_final_distance_to_goal": 3.9889178097623224,
    "collisions": 132
  },
  "lora": {
    "success_0_5": 0,
    "success_3": 1,
    "mean_spl_0_5": 0.0,
    "mean_final_distance_to_goal": 4.686244300975281,
    "collisions": 45
  }
}
```

If the source JSON differs, implementation must fail and surface the drift; it must not silently preserve the table above.

## Task 1: Build the Public-Content and Evidence Contract

**Files:**

- Create: `scripts/challenge_video_contract.py`
- Create: `tests/test_challenge_video_contract.py`

### Step 1: Write the failing contract tests

Cover these cases:

```python
class ChallengeVideoContractTests(unittest.TestCase):
    def test_extracts_metrics_from_authoritative_json(self):
        facts = evidence_snapshot(ROOT)
        self.assertEqual(facts["heldout_episode_ids"], [f"eval-{seed}" for seed in range(2001, 2011)])
        self.assertEqual(facts["base"]["success_0_5"], 0)
        self.assertEqual(facts["lora"]["success_0_5"], 0)
        self.assertEqual(facts["base"]["success_3"], 2)
        self.assertEqual(facts["lora"]["success_3"], 1)
        self.assertEqual(facts["lora_training"]["updates"], 59)
        self.assertEqual(facts["lora_training"]["loss_first"], 0.4167)
        self.assertEqual(facts["lora_training"]["loss_last"], 0.0823)

    def test_rejects_forbidden_public_wording(self):
        for term in FORBIDDEN_PUBLIC_TERMS:
            self.assertEqual(scan_public_text(f"开头{term}结尾"), [term])

    def test_rejects_sensitive_values_and_absolute_paths(self):
        text = "邮箱 a@example.com，服务 10.0.0.1，本地 /Users/name/work，远端 /root/work"
        self.assertGreaterEqual(len(scan_sensitive_text(text)), 4)

    def test_certificate_copy_is_conditional(self):
        self.assertEqual(validate_claims("完成后保证获得证书"), ["certificate claim must be conditional"])
        self.assertEqual(validate_claims(APPROVED_CERTIFICATE_COPY), [])
```

Run:

```bash
python3 -m unittest tests.test_challenge_video_contract -v
```

Expected: `ImportError` because `scripts.challenge_video_contract` does not exist.

### Step 2: Implement the smallest contract module

Implement:

```python
FORBIDDEN_PUBLIC_TERMS = (
    "课程", "PDF", "指南", "私有包", "原样复现", "等价适配", "非官方适配"
)

def evidence_snapshot(root: Path) -> dict[str, Any]: ...
def scan_public_text(text: str) -> list[str]: ...
def scan_sensitive_text(text: str) -> list[str]: ...
def validate_claims(text: str) -> list[str]: ...
def public_repo_path(path: Path, root: Path) -> str: ...
def sha256(path: Path) -> str: ...
```

Requirements:

- Read Base and LoRA results from `eval_result.json`.
- Read LoRA training facts from `stage2_result_v2.json`.
- Assert `same_heldout_batch is True`, exactly ten IDs, and identical ordered IDs inside both model evaluations.
- Preserve full precision in JSON metadata; round only for display text.
- Convert collisions to the public description “安全门拦截的前进尝试”, not physical robot impacts.
- Keep public paths repository-relative.
- Sensitive regexes must catch email, IPv4, common cloud instance identifiers, `/Users/...`, `/root/...`, `ssh ...`, and login/credential labels.

### Step 3: Run tests and commit

```bash
python3 -m unittest tests.test_challenge_video_contract -v
git add aima-open-session-experiment/scripts/challenge_video_contract.py \
        aima-open-session-experiment/tests/test_challenge_video_contract.py
git commit -m "feat(media): add challenge evidence contract"
```

Expected: all contract tests pass.

## Task 2: Build the 11-Minute Evidence Storyboard

**Files:**

- Create: `scripts/build_challenge_video_manifest.py`
- Create: `tests/test_challenge_video_manifest.py`
- Generate: `content/challenge-video/challenge-source.json`
- Generate: `content/challenge-video/challenge-manifest.json`
- Generate: `content/challenge-video/narration-sections.json`

### Step 1: Write failing storyboard tests

Tests must assert:

```python
manifest = build_manifest(ROOT)
segments = manifest["segments"]
total = sum(item["duration_s"] for item in segments)
real = sum(item["duration_s"] for item in segments if item["source_type"] == "real_recording")

self.assertGreaterEqual(total, 600)
self.assertLessEqual(total, 720)
self.assertGreaterEqual(real / total, 0.80)
self.assertEqual(manifest["chapter_ids"], [
    "hook", "baseline", "operation", "data", "training", "paired_eval", "innovation", "closing"
])
self.assertTrue(all(item["duration_s"] <= 4 for item in segments if item["source_type"] != "real_recording"))
self.assertEqual(len(manifest["paired_episode_ids"]), 10)
self.assertEqual(len(manifest["paired_replays"]), 20)
self.assertEqual(len(set(manifest["paired_replays"])), 20)
self.assertEqual(scan_public_bundle(manifest), [])
```

Also test:

- Every segment has `segment_id`, `chapter_id`, `source`, `source_type`, `evidence_ref`, `duration_s`, `source_in_s`, `source_out_s`, `narration_section`, `subtitle`, `overlay`, and `public_label`.
- `public_label` is only `真实录屏`, `真实结果`, or `流程示意`.
- Every source and evidence path resolves inside the repository and exists.
- Real footage is not counted by screenshot or chart duration.
- Source windows never exceed the real clip duration unless `allow_loop` is explicitly true.
- Chapter totals match the approved schedule within ±5 seconds:
  - hook: 35 seconds
  - baseline: 45 seconds
  - operation: 100 seconds
  - data: 100 seconds
  - training: 120 seconds
  - paired evaluation: 150 seconds
  - innovation: 70 seconds
  - closing: 40 seconds

Run:

```bash
python3 -m unittest tests.test_challenge_video_manifest -v
```

Expected: failure because the builder does not exist.

### Step 2: Implement the storyboard builder

Use these source groups:

```python
REAL_OPERATION = [
    "assets/series/recapture/raw/stage0-rgb-replay.mp4",
    "assets/series/recapture/raw/stage0-blocked-replay.mp4",
]
REAL_DATA = [
    "assets/series/recapture/raw/stage1-train1001-replay.mp4",
]
REAL_TRAINING = [
    "assets/series/recapture/raw/stage2-single-batch-replay.mp4",
    "assets/series/recapture/raw/stage2-adapter-reload-replay.mp4",
]
PAIRED = [
    f"assets/series/recapture/canonical/{variant}-eval-{seed}-annotated.mp4"
    for seed in range(2001, 2011)
    for variant in ("base", "lora")
]
```

Add short evidence inserts from:

- `assets/screenshots/v3/stage0-validation.png`
- `assets/screenshots/v3/stage1-validation.png`
- `assets/screenshots/v3/stage2-gates.png`
- `assets/screenshots/v3/stage2-loss-curve.png`
- `assets/screenshots/v3/stage3-paired-metrics.png`
- `assets/screenshots/v3/stage3-episode-distances.png`
- `assets/plots/schema-sidecar.png`
- `assets/plots/metrics-base-lora.png`
- `assets/plots/action-counts.png`
- `assets/plots/next-roadmap.png`

Narration requirements:

- 2,200–2,700 Chinese characters, excluding punctuation and JSON keys.
- Start from a visual navigation challenge, not a generic greeting.
- Explain action IDs `0/1/2/3`, 0.25 m forward, 15° turns, two-frame wait, RGB/depth/pose synchronization, and blocked pose invariance.
- Explain 3 smoke episodes, 50 train seeds, 10 held-out seeds, `annotations.json`, and sidecar roles.
- Explain the isolated environments and LoRA settings: `r=8`, `alpha=16`, dropout `0.05`, one epoch, batch one, LR `2e-5`, BF16, gradient checkpointing.
- Explain that 59 finite updates and lower loss prove training ran, not that navigation improved.
- Show every held-out ID once as a Base/LoRA pair. Give 2001 and one failure-heavy episode longer commentary; use a faster montage for the other eight pairs.
- State the exact 0.5 m main metric and the 3 m auxiliary observation.
- Explain that collision counts are safety-gate blocks.
- Explain four innovation directions:
  - scene and target diversity;
  - data diversity and hard negatives;
  - memory/planning/safety-gate algorithm changes;
  - paired evaluation, failure taxonomy, and reproducibility.
- Use the approved conditional certificate/resource wording.
- End exactly with:

  > 真正的挑战，不是做出一段演示，而是让每一个结果都经得起复核。

### Step 3: Generate and validate source files

```bash
python3 scripts/build_challenge_video_manifest.py \
  --output content/challenge-video/challenge-manifest.json \
  --source-output content/challenge-video/challenge-source.json \
  --narration-output content/challenge-video/narration-sections.json
python3 -m unittest tests.test_challenge_video_manifest -v
```

Expected:

- 600–720 seconds.
- Real-recording ratio ≥ 0.80.
- Twenty distinct paired replay paths.
- No public-wording or sensitive-data hits.

### Step 4: Commit

```bash
git add aima-open-session-experiment/scripts/build_challenge_video_manifest.py \
        aima-open-session-experiment/tests/test_challenge_video_manifest.py \
        aima-open-session-experiment/content/challenge-video/challenge-source.json \
        aima-open-session-experiment/content/challenge-video/challenge-manifest.json \
        aima-open-session-experiment/content/challenge-video/narration-sections.json
git commit -m "feat(media): build challenge video storyboard"
```

## Task 3: Produce and Select a Natural Deep Male Voice

**Files:**

- Create: `scripts/synthesize_challenge_voice.py`
- Create: `tests/test_challenge_voice.py`
- Create: `content/challenge-video/voice-config.json`
- Generate: `content/challenge-video/voice-metadata.json`
- Generate ignored: `assets/challenge-video/auditions/*.mp3`
- Generate ignored: `assets/challenge-video/audio/*.mp3`

### Step 1: Write failing voice tests

Mock the Edge TTS subprocess or communicator. Test:

```python
self.assertEqual(split_sections(source)[0]["chapter_id"], "hook")
self.assertTrue(all(len(chunk["text"]) <= 260 for chunk in chunks))
self.assertEqual(pause_schedule("第一句。第二句。"), [320, 320])
self.assertEqual(metadata["section_count"], 8)
self.assertIn("sha256", metadata["sections"][0])
self.assertEqual(scan_public_bundle(metadata), [])
```

Also verify:

- A failed section retries at most three times.
- A zero-byte or undecodable MP3 is rejected.
- Section files are concatenated in manifest order.
- TTS metadata contains provider, voice, rate, pitch, generation time, input hash, output hash, and duration.
- The script never prints credentials or query strings.

Run:

```bash
python3 -m unittest tests.test_challenge_voice -v
```

Expected: failure because the synthesizer does not exist.

### Step 2: Implement voice auditions and sectional synthesis

Use three audition candidates:

```json
[
  {"voice": "zh-CN-YunjianNeural", "rate": "-6%", "pitch": "-6Hz"},
  {"voice": "zh-CN-YunxiNeural", "rate": "-8%", "pitch": "-4Hz"},
  {"voice": "zh-CN-YunyangNeural", "rate": "-7%", "pitch": "-5Hz"}
]
```

Do not assume availability. Query Edge TTS voices first and remove unavailable candidates. Generate the same 20–25 second audition copy for each available voice. Select `zh-CN-YunjianNeural` by default if it is available; otherwise use the first available male Mandarin candidate and record the fallback in metadata.

Synthesize by chapter and by chunks of no more than 260 Chinese characters. Current `edge-tts` no longer supports arbitrary custom SSML, so insert deterministic FFmpeg-generated silence clips between synthesized chunks instead of sending `<break>` tags. Add natural pauses:

- clause pause: 120–180 ms;
- sentence pause: 260–360 ms;
- paragraph pause: 500–700 ms;
- chapter pause: 800–1000 ms.

Do not use a single 11-minute TTS request.

### Step 3: Run unit tests, create auditions, and synthesize

```bash
python3 -m unittest tests.test_challenge_voice -v
python3 scripts/synthesize_challenge_voice.py \
  --narration content/challenge-video/narration-sections.json \
  --config content/challenge-video/voice-config.json \
  --audition-dir assets/challenge-video/auditions \
  --output-dir assets/challenge-video/audio \
  --metadata content/challenge-video/voice-metadata.json
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  assets/challenge-video/audio/challenge-voice.mp3
```

Expected:

- All eight chapter files decode.
- The combined voice track is long enough to cover the narration without speaking faster than the configured target.
- No section silently disappears.
- The selected voice is recorded in `voice-config.json` and `voice-metadata.json`.

### Step 4: Listen to the audition and commit metadata

Manual acceptance:

- no obvious robotic truncation;
- no repeated phrases;
- numbers such as `0.5 米`, `LoRA`, and `StreamVLN` are understandable;
- tone is calm, deep, and explanatory;
- pauses sound intentional.

```bash
git add aima-open-session-experiment/scripts/synthesize_challenge_voice.py \
        aima-open-session-experiment/tests/test_challenge_voice.py \
        aima-open-session-experiment/content/challenge-video/voice-config.json \
        aima-open-session-experiment/content/challenge-video/voice-metadata.json
git commit -m "feat(media): add sectional challenge narration"
```

## Task 4: Implement the Evidence-First Video Renderer

**Files:**

- Create: `scripts/build_challenge_video.py`
- Create: `tests/test_challenge_video_renderer.py`
- Modify: `.gitignore`
- Generate ignored: `assets/challenge-video/work/*`
- Generate ignored: `assets/challenge-video/final/geniesim-streamvln-challenge.mp4`
- Generate: `assets/challenge-video/final/geniesim-streamvln-challenge.srt`
- Generate: `assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json`

### Step 1: Write renderer helper tests

Test pure helpers without encoding the full video:

```python
self.assertEqual(dimensions(), (1920, 1080))
self.assertEqual(wrap_subtitle("一二三四五六七八九十", limit=8), ["一二三四五六七八", "九十"])
self.assertEqual(len([line for line in wrap_subtitle(text) if len(line) > 16]), 0)
self.assertEqual(source_window({"source_in_s": 2, "source_out_s": 7}), (2.0, 7.0))
self.assertEqual(public_label("real_recording"), "真实录屏")
self.assertEqual(public_label("metric_animation"), "真实结果")
self.assertEqual(public_label("diagram"), "流程示意")
```

Test the generated FFmpeg filter graph:

- contains scale/pad to 1920×1080;
- contains `fps=30`;
- contains no forced infinite loop for real video unless `allow_loop` is true;
- includes 300–500 ms crossfades only at chapter boundaries;
- ducks BGM beneath narration by 10–12 dB;
- normalizes the final mix toward -16 LUFS and -1 dBTP;
- outputs AAC 48 kHz stereo.

Run:

```bash
python3 -m unittest tests.test_challenge_video_renderer -v
```

Expected: failure because the renderer does not exist.

### Step 2: Implement segment rendering

Reuse small, stable helpers from `build_series_media.py` by import where practical, but do not change the existing four-stage renderer.

Renderer behavior:

- Preserve real video motion; do not replace it with a still frame.
- Crop account bars, remote addresses, instance IDs, and connection details using manifest-defined safe rectangles.
- For terminal footage, add a dark focus mask so only the current command/result is prominent.
- For canonical trajectory clips, preserve the existing action ID, target distance, blocked status, and trajectory overlays.
- Use source timestamps; do not restart every clip at zero.
- If a source clip is shorter than its allocated window, split the segment across another real source instead of silently looping.
- Give still evidence images a slow 2–4% pan/zoom, but cap each at four seconds.
- Place labels in the upper safe area and subtitles in the lower safe area.
- Burn a concise two-line subtitle into the video while also producing a detachable SRT.
- Keep each subtitle line at no more than 16 Chinese characters.
- Show only three visual labels: `真实录屏`, `真实结果`, `流程示意`.
- Use an original or license-recorded BGM from the existing project. If no license record exists, render without BGM rather than using an unverified track.

### Step 3: Render a 60-second style sample

```bash
python3 scripts/build_challenge_video.py \
  --manifest content/challenge-video/challenge-manifest.json \
  --voice assets/challenge-video/audio/challenge-voice.mp3 \
  --output assets/challenge-video/preview/style-sample-60s.mp4 \
  --duration 60 \
  --encoder-profile videotoolbox
```

Manual acceptance:

- at least 80% of the first minute is moving real footage;
- no static image remains unchanged longer than four seconds;
- subtitles are readable and do not cover action/distance overlays;
- voice is clearly louder than BGM;
- no forbidden wording or sensitive information is visible;
- pace resembles a continuous technical walkthrough, not an AI card slideshow.

### Step 4: Render the full master

```bash
python3 scripts/build_challenge_video.py \
  --manifest content/challenge-video/challenge-manifest.json \
  --voice assets/challenge-video/audio/challenge-voice.mp3 \
  --output assets/challenge-video/final/geniesim-streamvln-challenge.mp4 \
  --srt assets/challenge-video/final/geniesim-streamvln-challenge.srt \
  --metadata assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json \
  --encoder-profile videotoolbox
```

If VideoToolbox fails, rerun with `--encoder-profile libx264`; record the encoder used in the media manifest.

### Step 5: Commit renderer and small artifacts

Add these ignore rules:

```gitignore
assets/challenge-video/**/*.mp4
assets/challenge-video/**/*.mp3
assets/challenge-video/**/*.wav
assets/challenge-video/work/
assets/challenge-video/auditions/
```

Then:

```bash
python3 -m unittest tests.test_challenge_video_renderer -v
git add aima-open-session-experiment/.gitignore \
        aima-open-session-experiment/scripts/build_challenge_video.py \
        aima-open-session-experiment/tests/test_challenge_video_renderer.py \
        aima-open-session-experiment/assets/challenge-video/final/geniesim-streamvln-challenge.srt \
        aima-open-session-experiment/assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json
git commit -m "feat(media): render evidence-first challenge video"
```

## Task 5: Verify Media, Pairing, Metrics, Wording, and Audio

**Files:**

- Create: `scripts/verify_challenge_video.py`
- Create: `tests/test_challenge_video_verification.py`
- Generate: `content/challenge-video/acceptance.json`
- Generate: `assets/challenge-video/preview/contact-sheet.jpg`

### Step 1: Write failing verification tests

Test the validators independently:

```python
self.assertEqual(validate_storyboard(build_manifest(ROOT), ROOT), [])
self.assertEqual(acceptance_status({"media": "passed", "storyboard": "passed", "text": "passed"}), "passed")
self.assertEqual(acceptance_status({"media": "passed", "storyboard": "failed", "text": "passed"}), "failed")
```

Mutation tests must fail when:

- duration is 599 or 721 seconds;
- real footage ratio is 0.799;
- a static segment is 4.1 seconds;
- one held-out Base replay is missing;
- one LoRA replay is duplicated;
- Base and LoRA held-out IDs differ;
- a metric differs from `eval_result.json`;
- narration contains a forbidden term;
- narration contains an email, IP, absolute path, instance ID, or SSH command;
- a certificate claim becomes unconditional;
- SRT has more than two lines or a line longer than 16 Chinese characters;
- an audio track is missing;
- loudness is outside -18 to -14 LUFS;
- true peak exceeds -1 dBTP;
- one-second black video is detected.

Run:

```bash
python3 -m unittest tests.test_challenge_video_verification -v
```

Expected: failure because the verifier does not exist.

### Step 2: Implement shallow and deep verification

Shallow checks:

- storyboard schema and source existence;
- 600–720 seconds;
- real recording ratio ≥ 0.80;
- non-real segments ≤ 4 seconds;
- exactly ten ordered held-out IDs and twenty distinct canonical replays;
- exact metric and training fact snapshots;
- SRT line and timing rules;
- public and sensitive term scan over JSON, Markdown, SRT, and overlay source text;
- all paths remain inside the repository;
- media manifest hashes match generated files.

Deep checks:

- ffprobe: H.264, 1920×1080, 30 fps;
- ffprobe: AAC, 48 kHz, stereo;
- FFmpeg blackdetect: no interval ≥1 second;
- FFmpeg ebur128: -18 to -14 LUFS and true peak ≤ -1 dBTP;
- decode video from start to end with exit code zero;
- sample a frame every 30 seconds and build a contact sheet;
- run OCR on sampled frames when Tesseract is available; otherwise mark OCR as `not_available` and require source-text plus manual contact-sheet review;
- detect frozen intervals longer than four seconds outside explicitly animated evidence inserts;
- verify BGM provenance and hash when BGM is present.

### Step 3: Run the verifier

```bash
python3 scripts/verify_challenge_video.py \
  --manifest content/challenge-video/challenge-manifest.json \
  --video assets/challenge-video/final/geniesim-streamvln-challenge.mp4 \
  --srt assets/challenge-video/final/geniesim-streamvln-challenge.srt \
  --media-manifest assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json \
  --eval experiments/exp02-equivalent-v3/eval_result.json \
  --training-result experiments/exp02-equivalent-v3/stage2_result_v2.json \
  --contact-sheet assets/challenge-video/preview/contact-sheet.jpg \
  --output content/challenge-video/acceptance.json
```

Expected:

```json
{
  "status": "passed",
  "publishable_media_ready": true,
  "duration_check": "passed",
  "real_recording_ratio_check": "passed",
  "paired_trajectory_check": "passed",
  "metric_check": "passed",
  "public_text_check": "passed",
  "sensitive_scan": "passed",
  "decode_check": "passed",
  "audio_check": "passed"
}
```

### Step 4: Inspect contact sheet and commit

Open `assets/challenge-video/preview/contact-sheet.jpg` and verify:

- real operation footage is dominant;
- Base and LoRA footage is visually distinguishable;
- data and training screens are legible;
- no repeated card-like visual language dominates;
- no sensitive identifiers appear.

```bash
python3 -m unittest tests.test_challenge_video_verification -v
git add aima-open-session-experiment/scripts/verify_challenge_video.py \
        aima-open-session-experiment/tests/test_challenge_video_verification.py \
        aima-open-session-experiment/content/challenge-video/acceptance.json \
        aima-open-session-experiment/assets/challenge-video/preview/contact-sheet.jpg
git commit -m "test(media): verify challenge video delivery"
```

## Task 6: Create the Platform-Native Publish Package

**Files:**

- Create: `content/challenge-video/publish-package.json`
- Create: `content/challenge-video/publishing-state.json`
- Create: `article/challenge-video-publish-package.md`
- Extend: `tests/test_challenge_video_contract.py`

### Step 1: Add failing publish-copy tests

Assert:

- exactly three Bilibili title options;
- one 800–1200 Chinese-character description;
- exactly eight tags;
- one pinned comment;
- five FAQ entries;
- one dynamic teaser;
- no forbidden or sensitive wording;
- exact metrics match `evidence_snapshot`;
- certificate/resource wording is conditional;
- the publish state is `draft_not_submitted`;
- no public URL is invented.

Run:

```bash
python3 -m unittest tests.test_challenge_video_contract -v
```

Expected: new tests fail because publish files do not exist.

### Step 2: Write the publish package

Title directions:

1. Result-first:
   - `LoRA 训练完成，导航成功率为什么还是 0/10？`
2. Process-first:
   - `从 50 条轨迹到闭环评测：GenieSim × StreamVLN 全流程实录`
3. Challenge-first:
   - `让机器人真正听懂指令：一次具身导航 baseline 与创新挑战`

The description must include:

- what the video actually demonstrates;
- NVIDIA L40 48GB;
- scene, robot, action mapping, dataset split, LoRA training, paired evaluation;
- the honest 0/10 main result;
- 3 m auxiliary observation;
- collision-count interpretation;
- four innovation directions;
- conditional certificate/resource wording;
- a statement that metrics come from `eval_result.json`;
- no claim of public leaderboard performance.

Pinned comment:

- ask viewers which innovation direction they would test first;
- disclose that the main 0.5 m result is 0/10 for both variants;
- provide a compact evidence checklist.

### Step 3: Validate and commit

```bash
python3 -m unittest tests.test_challenge_video_contract -v
python3 scripts/verify_challenge_video.py --public-text-only \
  --manifest content/challenge-video/challenge-manifest.json \
  --publish-package content/challenge-video/publish-package.json
git add aima-open-session-experiment/content/challenge-video/publish-package.json \
        aima-open-session-experiment/content/challenge-video/publishing-state.json \
        aima-open-session-experiment/article/challenge-video-publish-package.md \
        aima-open-session-experiment/tests/test_challenge_video_contract.py
git commit -m "docs(media): add challenge video publish package"
```

## Task 7: Run the Full Verification Loop

**Files:**

- Modify only if necessary: files created in Tasks 1–6
- Modify: `README.md`

### Step 1: Run focused tests

```bash
python3 -m unittest \
  tests.test_challenge_video_contract \
  tests.test_challenge_video_manifest \
  tests.test_challenge_voice \
  tests.test_challenge_video_renderer \
  tests.test_challenge_video_verification -v
```

Expected: all focused tests pass.

### Step 2: Run the existing regression suite

```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests pass. The existing four-stage manifests and media behavior remain unchanged.

### Step 3: Rebuild from source and compare

```bash
python3 scripts/build_challenge_video_manifest.py \
  --output content/challenge-video/challenge-manifest.json \
  --source-output content/challenge-video/challenge-source.json \
  --narration-output content/challenge-video/narration-sections.json
python3 scripts/verify_challenge_video.py \
  --manifest content/challenge-video/challenge-manifest.json \
  --video assets/challenge-video/final/geniesim-streamvln-challenge.mp4 \
  --srt assets/challenge-video/final/geniesim-streamvln-challenge.srt \
  --media-manifest assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json \
  --eval experiments/exp02-equivalent-v3/eval_result.json \
  --training-result experiments/exp02-equivalent-v3/stage2_result_v2.json \
  --contact-sheet assets/challenge-video/preview/contact-sheet.jpg \
  --output content/challenge-video/acceptance.json
```

Expected: rebuilding the manifest is deterministic and the acceptance report remains `passed`.

### Step 4: Update the README

Add a concise “Navigation challenge video” section with:

- video purpose;
- source manifest path;
- authoritative metrics path;
- generated master path;
- acceptance path;
- regeneration commands;
- note that large audio/video outputs are ignored;
- publish state remains draft until user completes account login, cover review, and final submission.

Do not reuse public wording from old content if it contains any forbidden term.

### Step 5: Review diff and commit

```bash
git diff --check
git status --short
git diff -- aima-open-session-experiment/README.md \
  aima-open-session-experiment/content/challenge-video \
  aima-open-session-experiment/article/challenge-video-publish-package.md \
  aima-open-session-experiment/scripts/challenge_video_contract.py \
  aima-open-session-experiment/scripts/build_challenge_video_manifest.py \
  aima-open-session-experiment/scripts/synthesize_challenge_voice.py \
  aima-open-session-experiment/scripts/build_challenge_video.py \
  aima-open-session-experiment/scripts/verify_challenge_video.py \
  aima-open-session-experiment/tests/test_challenge_video_contract.py \
  aima-open-session-experiment/tests/test_challenge_video_manifest.py \
  aima-open-session-experiment/tests/test_challenge_voice.py \
  aima-open-session-experiment/tests/test_challenge_video_renderer.py \
  aima-open-session-experiment/tests/test_challenge_video_verification.py
git add aima-open-session-experiment/README.md
git commit -m "docs(media): document challenge video workflow"
```

Before committing, verify that no user-moved files under `assets/series/智元实验*` and no unrelated deletions appear in the staged diff:

```bash
git diff --cached --name-only
```

## Task 8: Prepare the Draft for User-Controlled Publishing

**Files:**

- Modify: `content/challenge-video/publishing-state.json`

### Step 1: Confirm local delivery status

Required local state:

```json
{
  "asset_status": "completed",
  "acceptance_status": "passed",
  "platform": "bilibili",
  "submission_status": "draft_not_submitted",
  "public_url": null,
  "review_required": [
    "voice",
    "cover",
    "title",
    "final_submit"
  ]
}
```

### Step 2: Stop before irreversible publishing

The implementation may open the Bilibili creator draft page and populate a reversible draft only after the user asks to publish. It must not:

- bypass a QR code or verification code;
- choose the final cover without user review;
- click the final publish/submit button;
- claim a public URL before platform review.

### Step 3: Final handoff checklist

Report:

- master video path and duration;
- selected voice and audition paths;
- SRT path;
- contact sheet path;
- acceptance report path and status;
- three title choices;
- draft publishing state;
- exact unresolved user actions.

Do not mark the work publicly released until an unauthenticated window can open the approved public URL.

## Final Acceptance Checklist

- [ ] Video is 600–720 seconds.
- [ ] Video is H.264, 1920×1080, 30 fps.
- [ ] Audio is AAC, 48 kHz, stereo.
- [ ] Integrated loudness is -18 to -14 LUFS.
- [ ] True peak is ≤ -1 dBTP.
- [ ] Real moving footage ratio is ≥ 80%.
- [ ] Static evidence inserts are ≤ 4 seconds each.
- [ ] The video shows real operations, data structure, training, Base/LoRA pairs, metrics, and innovation challenges.
- [ ] All ten held-out IDs appear in ordered Base/LoRA pairs.
- [ ] Main `success@0.5m` is truthfully shown as 0/10 for both variants.
- [ ] Auxiliary `success@3m` is truthfully shown as Base 2/10 and LoRA 1/10.
- [ ] Mean final distance and safety-block counts match `eval_result.json`.
- [ ] LoRA updates, loss, memory, and reload facts match `stage2_result_v2.json`.
- [ ] No forbidden public wording appears in title, narration, SRT, overlays, cover, description, or pinned comment.
- [ ] No account, email, IP, instance ID, connection detail, credential, or absolute path appears.
- [ ] Certificate and resource claims are conditional.
- [ ] The final sentence matches the approved wording.
- [ ] `content/challenge-video/acceptance.json` reports `passed`.
- [ ] Publishing remains a user-confirmed draft action.
