# 抖音旁白音轨实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为现有 90 秒中文竖屏实验视频加入稳重的中文神经网络男声旁白，并保留无声原版。

**Architecture:** 旁白文本单独保存，使用 Microsoft Edge Neural `zh-CN-YunyangNeural` 生成 MP3；FFmpeg 对音频做响度标准化、补静音并裁剪到 90 秒，再与原视频复用视频流合成带旁白版本。原始视频不覆盖，新的音频、字幕和视频进入独立文件名并写入内容清单。

**Tech Stack:** Python `edge_tts`、FFmpeg、AAC、H.264、JSON manifest。

---

### Task 1: 固定旁白文本

**Files:**
- Create: `assets/audio/douyin-voiceover-yunyang.txt`

**Step 1:** 保存全中文旁白，包含真实截图说明、基础模型与低秩适配指标及非官方边界。

**Step 2:** 检查文本不含邮箱、地址、实例编号和“个人实验”字样。

### Task 2: 生成并验证神经网络音频

**Files:**
- Create: `assets/audio/douyin-voiceover-yunyang.mp3`
- Create: `assets/audio/douyin-voiceover-yunyang.srt`

**Step 1:** 用 `python3 -m edge_tts` 与 `zh-CN-YunyangNeural` 生成音频和字幕。

**Step 2:** 用 `ffprobe` 检查音频可解码、时长足够且采样率正常。

### Task 3: 合成带旁白视频

**Files:**
- Create: `assets/videos/stage1-smoke-retrospective-vertical-90s-voiceover.mp4`

**Step 1:** 音频执行响度标准化，必要时补静音或裁剪至 90 秒。

**Step 2:** 视频复用原始 H.264 画面，音频编码为 AAC，生成约 90 秒带旁白版本。

**Step 3:** 用 `ffprobe` 与抽帧检查视频仍为 1080×1920、30fps，且音频流存在。

### Task 4: 清单、测试与交付

**Files:**
- Modify: `article/抖音-智元布道师图文稿.md`
- Modify: `docs/evidence/douyin-media-run-manifest.json`

**Step 1:** 在文案中标明音色、无版权音乐和新视频文件。

**Step 2:** 更新 manifest，记录旁白文本、MP3、SRT 与带声音 MP4 的哈希。

**Step 3:** 运行测试、哈希校验和 `git diff --check`；只保存抖音草稿，不执行发布。
