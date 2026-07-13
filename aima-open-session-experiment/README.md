# 智元精灵工坊 AIMA：GenieSim + StreamVLN 实验档案

本目录记录依据《智元精灵工坊 AIMA 技术开发指南》制作的个人、非官方 GenieSim × StreamVLN 适配实验，以及面向被宣传者的抖音素材。

> 重要声明：流程参考 AIMA 指南，但未使用课程私有适配包；导航后端是碰撞感知的刚体 G2 代理，不代表真实人形步态，也不是 AgiBot 官方集成。

## 当前状态

- GPUFree L40 48GB、100GB 持久盘、SSH 公钥登录与 Isaac Sim 5.1/Genie Sim 3.0 已验证。
- Stage 0 loopback 服务已真实启动并验证 reset/step/重复 request_id/close；USD AABB 投影触发引擎安全退出，因此运行配置显式使用安全 fallback 栅格。
- Stage 1 已采集 3 条冒烟、50 条训练和 10 条固定种子评测轨迹；公开 annotation 通过严格校验，完整 STOP/depth/轨迹保存在 sidecar。
- StreamVLN 代码、real-world checkpoint 和 SigLIP pinned revision 已核验并下载到持久盘；Python 3.9 依赖与模型分片加载成功，但 LoRA 在首个训练 batch 的 logits shape 校验失败，因此没有 adapter，base/LoRA 推理保持 `not_run`。
- 失败 gate 详见 [`stage2_result.json`](experiments/exp01-baseline/stage2_result.json) 与 [`stage2-failure.log`](runs/2026-07-13/stage2-failure.log)；这是透明的非官方适配失败复盘，不是模型成功案例。
- 所有结论都由真实日志、媒体和 `eval_result.json` 支撑；未完成环节保留 `blocked/not_run` 状态，不用占位内容替代。

## 导航

- [实施计划](docs/plans/2026-07-13-aima-vln-experiment.md)
- [00：准备、资源与安全](docs/00-准备-资源与安全.md)
- [01：Stage 0 仿真验证](docs/01-stage0-仿真环境验证.md)
- [02：Stage 1 数据采集](docs/02-stage1-数据采集.md)
- [03：Stage 2 LoRA 微调](docs/03-stage2-lora微调.md)
- [04：Stage 3 实时推理评测](docs/04-stage3-实时推理评测.md)
- [05：结果分析与排障](docs/05-结果分析与排障.md)
- [06：课程资产检索与阻塞记录](docs/06-课程资产检索与阻塞记录.md)
- [实验运行日志](runs/2026-07-13/session-log.md)
- [抖音布道文章](article/抖音-智元布道师图文稿.md)

## 素材目录

- `assets/screenshots/`：关键界面、命令和结果截图。
- `assets/gifs/`：短动作、数据采集与推理过程动图。
- `assets/videos/`：原始录屏和完整导航视频。
- `assets/plots/`：训练曲线、轨迹图和评测可视化。

## 已有真实素材

- [Stage 1 控制器 GIF](assets/gifs/stage1-smoke-controller.gif)
- [45–60 秒竖屏 MP4](assets/videos/stage1-smoke-retrospective-vertical.mp4)
- [8 张抖音轮播图](assets/carousel/)
- [冒烟 RGB 帧](assets/screenshots/P1-smoke-0000.jpg)

## 安全边界

账号密码、身份证信息、SSH 私钥、实例密码、Cookie、Token、UUID、Tunnel Endpoint、IP、实例 ID 和连接命令不得进入本目录或 Git 历史。所有公开截图和视频在引用前必须完成裁剪或打码。StreamVLN 仓库与 checkpoint 未明确声明适用于本实验的许可证；本目录只作个人非商业研究演示，不传播权重。
