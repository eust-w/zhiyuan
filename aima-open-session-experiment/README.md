# GenieSim × StreamVLN 实验目录

[返回项目首页](../README.md) · [MIT 许可证](../LICENSE) · [第三方许可与素材边界](../THIRD_PARTY_NOTICES.md)

这里保存仿真适配器、数据与训练工具、配对评测结果，以及阶段文档和媒体归档。首次访问请先看项目首页；它集中说明了用途、快速检查、真实结果和复现限制。

## 结果与证据

主评测：[exp02-equivalent-v3/eval_result.json](experiments/exp02-equivalent-v3/eval_result.json)。Base 与 LoRA 在同一批 `eval-2001…eval-2010` 上的 success@0.5m 均为 **0/10**；同文件中的控制器轨迹验证为 10/10，不能当作模型成绩。

| 需要查看的证据 | 文件 |
| --- | --- |
| 版本、配置及历史验收记录 | [run-manifest.json](experiments/exp02-equivalent-v3/run-manifest.json) |
| 数据结构验证记录 | [dataset-validation.json](experiments/exp02-equivalent-v3/dataset-validation.json) |
| 59 步训练与 adapter 重载 | [stage2_result_v2.json](experiments/exp02-equivalent-v3/stage2_result_v2.json) |
| 原始训练输出 | [stage2-train.stdout.log](experiments/exp02-equivalent-v3/logs/stage2-train.stdout.log) |
| 动作与安全门演示 | [Stage 0 GIF](assets/media/v3/stage0-keyboard-and-guard.gif) |
| 单条采集轨迹 | [Stage 1 GIF](assets/media/v3/stage1-train-1001.gif) |
| 单条模型轨迹 | [Base eval-2004 GIF](assets/media/v3/stage3-base-2004.gif) |

`collisions` 是前进安全门拦截计数；SPL 使用初始直线距离代理，不是标准 geodesic SPL。历史模型评测采用 head-depth 安全门，不能把独立 AABB 探针的结果当成同一次完整场景评测的能力。图像文件非空检查也不等于解码验证。详见[首页的限制说明](../README.md#当前已知限制)。

## 代码入口

以下模块功能不同，不可相互替代：

| 模块 | 用途 | 额外前提 |
| --- | --- | --- |
| `adapter.vln_app` | 启动仿真与本机 HTTP 服务 | Isaac Python、GenieSim、场景与机器人资产 |
| `adapter.collect_dataset` | 执行控制器采集并写入数据 | 已启动的服务、可写实验目录 |
| `adapter.stage2_preflight` | 数据/训练检查与兼容补丁 | 独立 StreamVLN checkout、模型环境、数据和权重 |
| `adapter.reload_adapter` | 新进程挂载 LoRA adapter | 基座、视觉塔、adapter 和模型依赖 |
| `adapter.model_closed_loop_eval` | 模型生成动作并驱动仿真 | 上述模型与服务、held-out sidecar |
| `adapter.evaluate_sidecars` | 汇总控制器轨迹 | 已存在的 sidecar；不执行模型推理 |
| `adapter.assemble_eval_result` | 组装并核对已有结果 | 已存在的评测 JSON；不执行模型推理 |

协议、动作空间和运行约束见 [adapter/README.md](adapter/README.md)。不要直接运行历史启动脚本中的固定路径；先检查 `PROJECT_ROOT`、`RUN_DIR`、`GENIE_SIM_ROOT`、Isaac Python 路径及场景配置。

## 阶段文档

- [Stage 0：仿真与动作验证](docs/01-stage0-仿真环境验证.md)
- [Stage 1：数据采集](docs/02-stage1-数据采集.md)
- [Stage 2：LoRA 微调](docs/03-stage2-lora微调.md)
- [Stage 3：模型闭环评测](docs/04-stage3-实时推理评测.md)
- [结果分析与排障](docs/05-结果分析与排障.md)

## 媒体归档

[导航挑战故事板](content/challenge-video/challenge-manifest.json)、[媒体清单](assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json)、[字幕](assets/challenge-video/final/geniesim-streamvln-challenge.srt)、[验收记录](content/challenge-video/acceptance.json) 与 [系列文案索引](article/series/README.md) 用于追溯历史制作过程，不是项目运行依赖。

长视频、原始数据和外部权重不能假定随 clone 获取。媒体生成脚本需要额外素材、字体、音频服务或编码工具；历史验收通过也不代表平台已经发布，发布记录见 [publishing-state.json](content/challenge-video/publishing-state.json)。媒体和场景衍生物不包含在自有代码的 MIT 许可内。
