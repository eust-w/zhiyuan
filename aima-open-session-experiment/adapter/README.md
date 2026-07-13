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

## 自采等价场景资产

新采集的每个 observation 会额外记录 USD 相机内参和 `camera_to_world`。在 Isaac Python 中可把同一批 RGB-D 融合成自有等价资产：

```bash
/isaac-sim/python.sh -m adapter.equivalent_assets \
  --root /root/gpufree-data/zhiyuan-aima/workspace/aima-open-session-experiment \
  --input-json /root/gpufree-data/zhiyuan-aima/workspace/aima-open-session-experiment/dataset/sidecar/*.json \
  --output-dir /root/gpufree-data/zhiyuan-aima/workspace/aima-open-session-experiment/equivalent-scene
```

输出包含 `sample.ply`、点云型 `sample.usda`、`sample.usdz` 和哈希清单。它们统一声明为 `geniesim-self-captured-equivalent/v1`，只能称为“仿真自采等价资产”，不能称为课程私有原件。全无限 depth fallback 帧会被拒绝，不进入点云。
