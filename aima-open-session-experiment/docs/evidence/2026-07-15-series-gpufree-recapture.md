# 四期教程 GPUFree 补录记录（Stage 0–3 样片素材已补，正片仍待重剪）

## 目的

为四期教程补录不超过预算的真实 GenieSim 画面，覆盖场景启动、Stage 0 动作、近障碍安全门、RGB/depth 同步、Stage 1 单条轨迹采集、Stage 2 单批训练与 adapter 重载，以及 Stage 3 base/LoRA 模型闭环轨迹。完整 50 条训练、10 条留出评测及全量 LoRA 训练不在补录轮次重复执行。

## 预算与保护

- L40/48G 启动前观察价为 ¥2.28/h。
- 新增算力硬上限为 ¥10。7 月 15 日轮次估算 ¥4.23；7 月 16 日轮次约运行 46 分钟，按相同单价估算 ¥1.75；合计估算 ¥5.98，低于硬上限。
- 已设置定时关机，并预留超过 20 分钟的收尾缓冲。
- 两轮补录结束后均先停止适配器、训练和闭环评测进程，再手动关机；控制台分别于 `2026-07-15 17:25:54 +08:00` 和 `2026-07-16 02:23:00 +08:00` 显示“已关机”。
- 不在公开证据中记录账号、IP、实例编号、连接地址或持久盘真实路径。
- 预算明细见 [`content/series/recapture-budget.json`](../../content/series/recapture-budget.json)。
- 脱敏关机状态见 [`2026-07-15-gpufree-shutdown.json`](./2026-07-15-gpufree-shutdown.json) 与 [`2026-07-16-gpufree-shutdown.json`](./2026-07-16-gpufree-shutdown.json)。

## 真实运行结果

Stage 0 使用 `market_00_g2`、G2 Omnipicker 和头部相机启动成功。为保证本轮媒体能够稳定采集，录制专用配置明确设置 `project_usd_aabbs: false`；运行日志中的占据来源为 `runtime_safe_fallback_no_usd_aabb`。等价 AABB/USD 验证仍由原有独立证据承担，不能把两者宣传成同一次运行。

本轮完成两组真实动作：

1. `W / S / A / D / Space` 全部返回成功，记录了 reset 加 5 个动作的 RGB、depth、4×4 位姿和状态。
2. 连续前进安全门探针共记录 reset、30 个前进动作和 STOP。第 1 次前进成功，第 2 至第 30 次均返回 `blocked=true`，阻挡来源为 `head_depth_forward_guard`。

第 1 次前进后的位姿矩阵与第 2 次被拒绝后的位姿矩阵完全相同，目标距离也保持 `3.423832802572252m`，满足“障碍前进被拒绝且位姿不变”的 Stage 0 证据要求。

## Stage 0 新增媒体

- `stage0-rgb-replay.mp4`：12 秒，1920×1080，30fps，H.264，来自 W/S/A/D/Space 的真实 RGB 帧。
- `stage0-blocked-replay.mp4`：16 秒，1920×1080，30fps，H.264，来自连续前进安全门探针的真实 RGB 帧。
- 两段素材均为无麦克风数据回放，公开使用时必须标注“真实数据回放（运行时安全配置）”。
- 完整动作、位姿、距离、媒体哈希与脱敏运行日志见 [`2026-07-15-stage0-recapture-evidence.json`](./2026-07-15-stage0-recapture-evidence.json)。

## Stage 1 单条采集补录

在相同运行时安全配置下，本轮重新采集固定种子 `1001` 的一条训练轨迹，最多执行 20 步。采集结果为 20 个导航步、正常 STOP、最终目标距离 `3.488957031003856m`、碰撞/阻挡计数 12。数据集校验器返回 1 条有效、0 条无效、无错误。

公开 `annotations.json` 保存 21 个动作与 21 帧 RGB，首动作是 `-1` 且不写最终 STOP；`geniesim-streamvln/v1` sidecar 保存 22 个完整动作并包含最终 STOP。该差异是 StreamVLN 公开训练格式与本实验完整运行证据的预期区别。

- `stage1-train1001-replay.mp4`：10.5 秒，1920×1080，30fps，H.264，来自该轨迹的真实头部相机 RGB 帧。
- Stage 1 60 秒样片将同一段真实采集素材分章节复用，真实素材时间占比 80%；这只是单 episode 的媒体复核，不替代原有 50 条训练、10 条评测数据集。
- 完整采集摘要、校验结果、动作统计和媒体哈希见 [`2026-07-15-stage1-recapture-evidence.json`](./2026-07-15-stage1-recapture-evidence.json)。

## Stage 2 单批训练与新进程重载补录

7 月 16 日在隔离的 StreamVLN Python 环境中重新执行一个真实更新步。训练集长度为 59，单步 `loss=0.4167`、`grad_norm=0.3841767907142639`、运行时间 `2.7822s`，模型输出正常保存。该结果只复核“单批前后向门”，全量 59 步训练仍引用原始训练结果，不能用单步补录替代。

adapter 第一次在新进程重载时真实失败，错误为 `ModuleNotFoundError: No module named 'utils'`。定位到新进程没有包含两个公开 StreamVLN 模块根目录后，显式补齐模块搜索路径并重新运行；四个检查点分片完成加载，返回 `status=passed`、`peft_type=LORA`、`lora_r=8`。公开视频保留“先失败、再定位、再通过”的顺序，不把失败记录删掉。

两段日志均先用原始文件哈希固化，再生成全中文脱敏回放；画面不包含远端路径、账号、地址或实例信息。完整结构化摘要见 [`2026-07-16-stage2-stage3-recapture-evidence.json`](./2026-07-16-stage2-stage3-recapture-evidence.json)。

## Stage 3 base/LoRA 模型闭环补录

本轮在同一个 `eval-2001` 上分别运行 StreamVLN base 与 LoRA，解码方式均为 `generate`，最大 20 步。动作由模型生成并逐步提交给 GenieSim adapter，视频来自每一步返回的真实头部相机 RGB，而不是 A* 控制器或卡片动画。公开回放逐帧叠加动作 ID、目标距离、blocked、碰撞和轨迹俯视图，叠加值直接从对应 JSON 读取。

| 变体 | success@0.5m | success@3m | 最终距离 | 最小距离 | 路径长度 | 步数 | 碰撞 | 动作计数（停/前/左/右） |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| base | 否 | 否 | 4.0668m | 3.8831m | 1.75m | 20 | 0 | 0 / 7 / 6 / 7 |
| LoRA | 否 | 否 | 4.4192m | 3.8558m | 2.50m | 20 | 0 | 0 / 10 / 4 / 6 |

这两条是媒体补录样本，不替代 canonical 十条配对评测。最终指标仍唯一来自 `experiments/exp02-equivalent-v3/eval_result.json`：base 与 LoRA 的 `success@0.5m` 均为 0/10，SPL 均为 0；3m 仅作为辅助观察，分别为 2/10 与 1/10。

## 失败边界

启用 AABB 代理的两次新鲜启动都在 `occupancy_proxy_direct_stage_scan` 后以退出码 0 结束，未进入 `adapter_ready`。尝试过的心跳改动在远端没有改善，已从本地工作树撤回，不会以未验证修复提交。

因此，本轮只能证明：安全配置下的动作、传感器同步和深度安全门真实有效；不能把它写成“本轮已重新验证 USD AABB 运行闭环”。

## 对四期交付的影响

Stage 0–3 四支 60 秒样片现在均达到 80% 真实素材时间占比，并通过 H.264、1080p、30fps、AAC、字幕行长、指标源与敏感信息检查。Stage 2 已接入真实训练/重载日志，Stage 3 已接入 base/LoRA 模型轨迹；但这些仍是风格样片，不是四支 10–15 分钟最终正片。系列状态更新为 `four_style_samples_ready_final_long_cuts_pending`，四个平台继续只保留草稿，不执行最终发布。
