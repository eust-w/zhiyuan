# 非官方 GenieSim × StreamVLN 适配层

本目录实现一个个人非商业研究适配，不是智元精灵工坊课程私有包，也不是 AgiBot 官方 GenieSim–StreamVLN 集成。

运行时约束：

- Isaac/GenieSim 进程只使用 GPUFree 的 `/isaac-sim/python.sh`。
- StreamVLN/PEFT 在持久盘内独立 Python 3.9 环境运行。
- 两者通过 `127.0.0.1:5802` 的 JSON HTTP 服务交换动作和观测。
- RGB、depth、pose、目标距离和 `blocked` 均写入实验根目录下的 `runtime/`。
- 模型权重、adapter、原始数据和长视频不进入 Git。
- 当前 GPUFree 资产的 USD AABB 投影会触发 SimulationApp clean shutdown；配置显式使用 `runtime_safe_fallback_no_usd_aabb`，因此不要把 fallback 结果描述成真实障碍栅格评测。

动作契约：`0=STOP`、`1=FORWARD(0.25m)`、`2=TURN_LEFT(15°)`、`3=TURN_RIGHT(15°)`。本次交付没有把键盘后退加入训练动作空间；若后续扩展键盘验证，后退只能作为 Stage 0 辅助动作。

采集入口：`python -m adapter.collect_dataset`；评测指标入口：`python -m adapter.evaluate_sidecars`；LoRA gate 入口：`python -m adapter.stage2_preflight`。
