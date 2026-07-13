# 智元精灵工坊 AIMA：GenieSim + StreamVLN 实验档案

本目录记录依据《智元精灵工坊 AIMA 技术开发指南》制作的非官方 GenieSim × StreamVLN 适配实验，以及面向被宣传者的抖音素材。

> 重要声明：流程参考 AIMA 指南，但未使用课程私有适配包；导航后端是碰撞感知的刚体 G2 代理，不代表真实人形步态，也不是 AgiBot 官方集成。

## 当前状态

- GPUFree L40 48GB、100GB 持久盘、SSH 公钥登录与 Isaac Sim 5.1/Genie Sim 3.0 已验证。
- Stage 0 已验证 W/S/A/D/Space、0.25m 前进、15° 转向、RGB/depth 和 head-depth 近障碍拒绝；危险前进被拒绝后位姿保持不变。USD AABB 投影仍受公开资产稳定性限制，健康接口显式标注 fallback + depth guard。
- Stage 1 已完成 3 条冒烟、50 条训练、10 条固定 held-out；严格校验为 50/50 与 10/10，公开 RGB 无全黑帧。1762 帧带标定 RGB-D 另生成 20 万点的等价 PLY/USDA/USDZ，并在新 Isaac 进程打开。
- Stage 2 已纠正上游 `qwen` 模板静默回退导致的假 0-loss 训练；最终 59 个真实更新步，loss `0.4167→0.0823`、峰值显存 27.19GiB、无 NaN/Inf，adapter 新进程重载通过。
- Stage 3 已完成真正的 StreamVLN base/LoRA → GenieSim 模型闭环；相同 `eval-2001…2010` 上两者 success@0.5m 都是 0/10。base 平均最终距离 3.989m、碰撞尝试 132 次；LoRA 4.686m、45 次。结果见唯一指标源 [`eval_result.json`](experiments/exp02-equivalent-v3/eval_result.json)，不能把控制器结果冒充模型成绩。
- 本轮按透明的“非官方等价适配失败复盘”交付；不提交 AgiBot Open Session 榜单。

## 导航

- [实施计划](docs/plans/2026-07-13-aima-vln-experiment.md)
- [00：准备、资源与安全](docs/00-准备-资源与安全.md)
- [01：Stage 0 仿真验证](docs/01-stage0-仿真环境验证.md)
- [02：Stage 1 数据采集](docs/02-stage1-数据采集.md)
- [03：Stage 2 LoRA 微调](docs/03-stage2-lora微调.md)
- [04：Stage 3 实时推理评测](docs/04-stage3-实时推理评测.md)
- [05：结果分析与排障](docs/05-结果分析与排障.md)
- [06：课程资产检索与阻塞记录](docs/06-课程资产检索与阻塞记录.md)
- [07：PDF 逐项验收与等价说明](docs/07-PDF逐项验收与等价说明.md)
- [实验运行日志](runs/2026-07-13/session-log.md)
- [抖音布道文章](article/抖音-智元布道师图文稿.md)

## 素材目录

- `assets/screenshots/`：关键界面、命令和结果截图。
- `assets/gifs/`：短动作、数据采集与推理过程动图。
- `assets/videos/`：原始录屏和完整导航视频。
- `assets/plots/`：训练曲线、轨迹图和评测可视化。

## 本轮真实素材

- [Stage 0 键盘与近障碍安全门 GIF](assets/media/v3/stage0-keyboard-and-guard.gif)
- [Stage 1 真实采集轨迹 GIF](assets/media/v3/stage1-train-1001.gif)
- [Stage 2 训练证据 GIF](assets/media/v3/stage2-training-evidence.gif)
- [Stage 3 真实模型轨迹 GIF](assets/media/v3/stage3-base-2004.gif)
- [20 张抖音轮播图](assets/carousel/)
- [55 秒竖屏 H.264 无音轨底片](assets/videos/douyin-vln-retrospective-55s.mp4)
- [55 秒竖屏 H.264 + AAC 沉稳男声成片](assets/videos/douyin-vln-retrospective-55s-voiceover.mp4)
- [沉稳男声文案与字幕](assets/audio/douyin-vln-voiceover-55s.txt)

## 安全边界

账号密码、身份证信息、SSH 私钥、实例密码、Cookie、Token、UUID、Tunnel Endpoint、IP、实例 ID 和连接命令不得进入本目录或 Git 历史。公开截图和视频引用前必须完成裁剪或打码。StreamVLN 仓库、checkpoint 与 adapter 的授权边界没有在本轮完成独立法律核验，因此基础权重与 adapter 只留在持久盘。本目录只作非商业研究演示。
