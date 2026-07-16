# 四期教程平台原生发布包

状态：final_long_media_ready_drafts_not_submitted。流程参考 AIMA 指南，采用公开组件与自采等价兼容资产；不声称复制课程私有资产，也不是课程官方方案。四期 10 分钟最终长片已完成并通过媒体验收，四个平台仍未提交；最终发布必须由用户登录、预览并确认。

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

## 四期 10 分钟最终长片

四期正片均为 1920×1080、30fps、H.264/AAC，单集 600 秒，真实实录时间占比 80%。全片解码、黑帧、响度、字幕行长、敏感信息与指标一致性检查已通过。第四期使用基础模型和低秩适配模型各 10 条、共 20 条 canonical held-out 真实轨迹；画面逐帧显示动作、目标距离、受阻、碰撞与轨迹，不再是单条样片或循环粗剪。

- [阶段零正片](../../assets/series/final-long/stage0/stage0.mp4) · [SRT](../../assets/series/final-long/stage0/stage0.srt) · [清单](../../assets/series/final-long/stage0/stage0-media-manifest.json)
- [阶段一正片](../../assets/series/final-long/stage1/stage1.mp4) · [SRT](../../assets/series/final-long/stage1/stage1.srt) · [清单](../../assets/series/final-long/stage1/stage1-media-manifest.json)
- [阶段二正片](../../assets/series/final-long/stage2/stage2.mp4) · [SRT](../../assets/series/final-long/stage2/stage2.srt) · [清单](../../assets/series/final-long/stage2/stage2-media-manifest.json)
- [阶段三正片](../../assets/series/final-long/stage3/stage3.mp4) · [SRT](../../assets/series/final-long/stage3/stage3.srt) · [清单](../../assets/series/final-long/stage3/stage3-media-manifest.json)
- [最终长片故事板](../../content/series/final-long-manifest.json)
- [最终长片验收](../../content/series/final-long-acceptance.json)
- [canonical 轨迹与长片结构化证据](../../docs/evidence/2026-07-16-canonical-final-long-evidence.json)

## Stage 0 新鲜实录样片

[Stage 0 60 秒样片](../../assets/series/stage0/stage0.mp4) 已接入本轮 GPUFree 真实 RGB 数据回放，时长 60 秒，真实录制素材占比 80%，包含 W/S/A/D/Space、两帧等待、头部深度安全门和阻挡后位姿不变证据。该文件保留为短平台预告；四期正片以本页“最终长片”目录为准。

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

## Stage 2 新鲜实录样片

[Stage 2 60 秒样片](../../assets/series/stage2/stage2.mp4) 已接入两段新鲜的真实日志回放：单批训练实测 `loss=0.4167`、`grad_norm=0.3842`，以及 adapter 首次因缺少模块路径失败、修复后 `status=passed` 的完整过程。原始日志保持私有，公开画面只显示脱敏后的可复核字段；真实素材时间占比 80%。

- [SRT](../../assets/series/stage2/stage2.srt)
- [媒体验收清单](../../assets/series/stage2/stage2-media-manifest.json)
- [Stage 2/3 结构化证据](../../docs/evidence/2026-07-16-stage2-stage3-recapture-evidence.json)

## Stage 3 新鲜实录样片

[Stage 3 60 秒样片](../../assets/series/stage3/stage3.mp4) 使用同一个 `eval-2001` 的 base 与 LoRA 真实头部相机轨迹，各占 24 秒。两条轨迹均由模型 `generate` 输出动作并驱动 GenieSim，不是控制器代跑；画面逐步叠加动作 ID、目标距离、blocked、碰撞和俯视轨迹，单条结果均未达到 0.5m。最终总体结论仍从同一批十条 `eval_result.json` 自动读取：base 与 LoRA 均为 0/10。

- [SRT](../../assets/series/stage3/stage3.srt)
- [媒体验收清单](../../assets/series/stage3/stage3-media-manifest.json)
- [Stage 2/3 结构化证据](../../docs/evidence/2026-07-16-stage2-stage3-recapture-evidence.json)
- [四期样片验收](../../content/series/series-media-acceptance.json)

## 归档：四期旧循环粗剪（不得发布）

以下文件只保留作历史归档，用于对照早期旁白与节奏；它们烧录“粗剪草稿｜旧素材片段复用｜未满足最终比例”标识，不是当前正片，也不得作为平台上传文件。当前可上传媒体仅指上方 `assets/series/final-long/` 下的四期最终长片。

- [Stage 0 粗剪](../../assets/series/long-drafts/stage0/stage0-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage0/stage0-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage0/stage0-rough-cut-manifest.json)
- [Stage 1 粗剪](../../assets/series/long-drafts/stage1/stage1-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage1/stage1-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage1/stage1-rough-cut-manifest.json)
- [Stage 2 粗剪](../../assets/series/long-drafts/stage2/stage2-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage2/stage2-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage2/stage2-rough-cut-manifest.json)
- [Stage 3 粗剪](../../assets/series/long-drafts/stage3/stage3-rough-cut-draft.mp4) · [SRT](../../assets/series/long-drafts/stage3/stage3-rough-cut-draft.srt) · [清单](../../assets/series/long-drafts/stage3/stage3-rough-cut-manifest.json)
