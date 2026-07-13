# 04｜Stage 3：StreamVLN → GenieSim 实时推理评测

状态：**已完成真正的 base/LoRA 模型闭环**。两个变体都在同一批 `eval-2001…2010` held-out episode 上完成了“读取 RGB/depth/指令 → StreamVLN 生成动作 → GenieSim 执行 → 回传位姿/距离/碰撞 → 汇总指标”。本轮没有达到目标半径 `0.5m` 的成功 episode，因此公开结论是“非官方适配失败复盘”，不是成功案例。

## 评测协议

- 场景：`market_00_g2`；目标：`red-target-marker`；动作：`0=STOP`、`1=前进 0.25m`、`2=左转 15°`、`3=右转 15°`。
- 同一批 `eval-2001…2010`，固定初始状态、指令和目标；base 与 LoRA 只切换模型权重。
- 每条 episode 重置 KV cache、动作队列和历史记忆，最大 200 步；非法输出安全转换为 STOP。
- 生成器使用真实 StreamVLN `generate` 路径，视觉输入来自 GenieSim 实时返回的 RGB/depth。为适配公开 StreamVLN 首帧 memory-token 的输入约定，适配层在没有历史 memory 时复用当前视觉特征作为一帧 memory；这是本项目明确记录的非官方兼容 shim，不宣称课程原样实现。
- 每个动作发送到 `127.0.0.1:5802`，服务端在 Isaac 主线程执行；动作后等待两个渲染帧，再保存 RGB、depth、pose、距离、blocked 和 collision。
- 指标唯一来源为 `experiments/exp01-baseline/eval_result.json`；每个变体的完整逐 episode 记录分别保存在 `base-model-eval.json` 和 `lora-model-eval.json`。

## 结果摘要

| 指标（10 episodes） | StreamVLN base | StreamVLN LoRA |
| --- | ---: | ---: |
| success@0.5m | **0/10** | **0/10** |
| success@3m | 2/10 | 2/10 |
| oracle success@0.5m | 1/10 | 0/10 |
| oracle success@3m | 5/10 | 5/10 |
| 平均最终距离 | 3.866m | 4.302m |
| 平均最小距离 | 2.396m | 2.876m |
| 平均路径长度 | 10.85m | 11.65m |
| 平均 SPL@0.5m | 0.000 | 0.000 |
| 平均 SPL@3m | 0.093 | 0.083 |
| 平均步数 | 110.9 | 117.3 |
| 碰撞次数 | 5 | 0 |

动作总计：base 为 `STOP 6 / forward 439 / left 303 / right 361`；LoRA 为 `STOP 7 / forward 466 / left 314 / right 386`。两者均在目标半径 `0.5m` 下为 0/10，不能把 `success@3m` 或 oracle 指标改写成任务成功。

## 逐 episode 可核验事实

两次运行的 source episode ID 完全一致：`eval-2001` 到 `eval-2010`。base 最终距离范围为 `0.732–10.256m`，LoRA 为 `2.736–6.518m`；base 有 5 次碰撞，LoRA 没有碰撞，但 LoRA 的平均最终距离和 SPL@3m 并未改善。每条记录都包含模型变体、随机种子、动作计数、步数、距离、碰撞和 GenieSim observation 路径，未以单条成功替代总体指标。

## 兼容性与限制

1. 当前启动健康接口报告 occupancy source 为 `runtime_safe_fallback_no_usd_aabb`。原始 G2 USD 在运行时遍历 malformed mesh 的 AABB 会触发 SimulationApp clean shutdown，本轮没有把 fallback 栅格宣传成课程私有 USD 的原样障碍评测。
2. depth annotator 在部分帧返回全非有限值时，后端记录 `depth_fallback=sensor_max_range`，写入有限的传感器最大量程值以保持协议可消费；这属于可审计的传感器兼容降级，不等于真实深度精度证明。
3. StreamVLN checkpoint、SigLIP 和 LoRA 仅在远程持久盘使用，不进入仓库，也不再分发权重。训练/重载成功只说明 adapter 可用，不代表导航质量。
4. 不向 AgiBot Open Session 榜单提交：本实验 sidecar 与课程 Challenge Tunnel/任务接口不兼容。

## 证据

- [唯一指标源](../experiments/exp01-baseline/eval_result.json)
- [base 完整结果](../experiments/exp01-baseline/base-model-eval.json)
- [LoRA 完整结果](../experiments/exp01-baseline/lora-model-eval.json)
- [base 模型日志](../experiments/exp01-baseline/model-logs/base-model-eval.log)
- [LoRA 模型日志](../experiments/exp01-baseline/model-logs/lora-model-eval.log)
- [真实 RGB GIF](../assets/gifs/stage1-smoke-controller.gif)
- [竖屏复盘视频](../assets/videos/stage1-smoke-retrospective-vertical.mp4)

## 结论与下一步

本轮已经完成从 StreamVLN base/LoRA 到 GenieSim 的真实闭环和同集评测，实验链路与指标证据完整；但按照预设的 `0.5m` 成功标准，结果是 **base 0/10、LoRA 0/10**，因此不能称为“模型导航成功”。下一轮应优先替换兼容 USD 资产、恢复真实 AABB + footprint inflation，修复深度传感器路径，并增加面向红色目标的有效训练样本，再复用同一组 held-out episode 做回归。
