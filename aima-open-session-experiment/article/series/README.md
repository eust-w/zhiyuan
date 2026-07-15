# 四期教程平台原生发布包

状态：draft_waiting_for_user_confirmation。流程参考 AIMA 指南，采用公开组件与自采等价兼容资产；不声称复制课程私有资产，也不是课程官方方案。

指标源：`experiments/exp02-equivalent-v3/eval_result.json`；主指标：`success@0.5m`。

本目录按 B 站、知乎、小红书、抖音分别编排，不把横屏成片直接裁切成竖屏稿。所有平台先保存草稿，用户完成最终发布。

- [bilibili-stage0.md](bilibili-stage0.md)
- [zhihu-stage0.md](zhihu-stage0.md)
- [xiaohongshu-stage0.md](xiaohongshu-stage0.md)
- [douyin-stage0.md](douyin-stage0.md)
- [小红书 Stage 0 卡片目录](../../assets/series/xiaohongshu/stage0/)
- [bilibili-stage1.md](bilibili-stage1.md)
- [zhihu-stage1.md](zhihu-stage1.md)
- [xiaohongshu-stage1.md](xiaohongshu-stage1.md)
- [douyin-stage1.md](douyin-stage1.md)
- [小红书 Stage 1 卡片目录](../../assets/series/xiaohongshu/stage1/)
- [bilibili-stage2.md](bilibili-stage2.md)
- [zhihu-stage2.md](zhihu-stage2.md)
- [xiaohongshu-stage2.md](xiaohongshu-stage2.md)
- [douyin-stage2.md](douyin-stage2.md)
- [小红书 Stage 2 卡片目录](../../assets/series/xiaohongshu/stage2/)
- [bilibili-stage3.md](bilibili-stage3.md)
- [zhihu-stage3.md](zhihu-stage3.md)
- [xiaohongshu-stage3.md](xiaohongshu-stage3.md)
- [douyin-stage3.md](douyin-stage3.md)
- [小红书 Stage 3 卡片目录](../../assets/series/xiaohongshu/stage3/)

## B 站封面草稿

- [Stage 0 封面](../../assets/series/covers/stage0-cover.png)
- [Stage 1 封面](../../assets/series/covers/stage1-cover.png)
- [Stage 2 封面](../../assets/series/covers/stage2-cover.png)
- [Stage 3 封面](../../assets/series/covers/stage3-cover.png)

## Stage 0 新鲜实录样片

[Stage 0 60 秒样片](../../assets/series/stage0/stage0.mp4) 已接入本轮 GPUFree 真实 RGB 数据回放，时长 60 秒，真实录制素材占比 80%，包含 W/S/A/D/Space、两帧等待、头部深度安全门和阻挡后位姿不变证据。该样片使用运行时安全配置，AABB/USD 证据单独披露；它只代表 Stage 0 样片通过，不代表四期正片完成。

- [SRT](../../assets/series/stage0/stage0.srt)
- [媒体验收清单](../../assets/series/stage0/stage0-media-manifest.json)
- [脱敏实验记录](../../docs/evidence/2026-07-15-series-gpufree-recapture.md)
- [结构化证据](../../docs/evidence/2026-07-15-stage0-recapture-evidence.json)

## Stage 1 新鲜实录样片

[Stage 1 60 秒样片](../../assets/series/stage1/stage1.mp4) 已接入固定种子 `1001` 的单条真实采集回放，时长 60 秒，真实录制素材占比 80%。该轨迹记录 20 个导航步、最终 STOP、RGB/depth/pose、目标距离与碰撞状态，并通过 1/1 数据集校验。它用于验证 Stage 1 的采集与格式说明，不替代既有完整 50 条训练和 10 条评测数据集。

- [SRT](../../assets/series/stage1/stage1.srt)
- [媒体验收清单](../../assets/series/stage1/stage1-media-manifest.json)
- [脱敏实验记录](../../docs/evidence/2026-07-15-series-gpufree-recapture.md)
- [结构化证据](../../docs/evidence/2026-07-15-stage1-recapture-evidence.json)

## 四期长片粗剪（明确不是最终发布）

以下视频已达到约 10–12 分钟，用于校对沉稳男声、章节节奏、字幕容器和音频混音；它们仍是本轮补录之前生成的循环粗剪，并烧录“粗剪草稿｜旧素材片段复用｜未满足最终比例”标识。Stage 2/3 新补录和四期最终比例未通过前，不得发布。

- [Stage 0 粗剪](../../assets/series/long-drafts/stage0/stage0-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage0/stage0-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage0/stage0-rough-cut-manifest.json)
- [Stage 1 粗剪](../../assets/series/long-drafts/stage1/stage1-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage1/stage1-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage1/stage1-rough-cut-manifest.json)
- [Stage 2 粗剪](../../assets/series/long-drafts/stage2/stage2-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage2/stage2-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage2/stage2-rough-cut-manifest.json)
- [Stage 3 粗剪](../../assets/series/long-drafts/stage3/stage3-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage3/stage3-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage3/stage3-rough-cut-manifest.json)
