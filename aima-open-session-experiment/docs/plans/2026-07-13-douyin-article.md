# 丰富抖音图文稿 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 8 张非官方 VLN 轮播提纲扩展成面向普通观众、同时保留技术证据和失败边界的抖音图文稿。

**Architecture:** 只修改 Markdown 文案，不修改仿真、数据或模型产物。文章按八张轮播图组织，每张包含标题、画面、字幕、正文和评论引导；所有数字从现有 `eval_result.json`、`stage2_result.json` 和真实媒体目录引用。

**Tech Stack:** Markdown、现有 JPG/GIF/MP4 素材、JSON 评测证据。

---

### Task 1: 扩写八张轮播脚本

**Files:**
- Modify: `article/抖音-智元布道师图文稿.md`
- Read: `experiments/exp01-baseline/eval_result.json`
- Read: `experiments/exp01-baseline/stage2_result.json`

**Steps:**

1. 以“英文指令如何变成动作”作为首图钩子。
2. 为每张图加入画面、屏幕字幕、口语化正文和评论引导。
3. 把训练通过、控制器结果和模型 base/LoRA 真实闭环结果拆成三个不同层级，禁止混写。
4. 补充封面标题、正文长文案、话题标签和发布前检查清单。

### Task 2: 校验素材与边界

**Files:**
- Modify: `article/抖音-智元布道师图文稿.md`

**Steps:**

1. 确认每张图引用的 JPG/GIF/MP4 路径真实存在。
2. 扫描文章中的邮箱、密码、IP、实例 ID、SSH 端口和私有权重路径。
3. 检查 Markdown 链接无断链，保留“用户确认最终提交”的发布流程。

### Task 3: 验证并提交

**Steps:**

1. 运行文章链接和敏感信息扫描。
2. 执行 `git diff --check`。
3. 提交文案变更，提交信息为 `docs: enrich douyin carousel copy`。
