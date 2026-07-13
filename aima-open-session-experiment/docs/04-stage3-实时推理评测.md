# 04｜Stage 3：实时推理与仿真评测

状态：模型基础/LoRA 配对评测 `not_run`；LoRA 训练首 batch 失败且没有 adapter。控制器闭环验证已写入唯一指标源 `experiments/exp01-baseline/eval_result.json`。

## 评测协议

- 同一 `eval-2001…2010` held-out episodes；每次重置 KV cache、动作队列和历史记忆。
- 最大 200 步；非法输出安全转换为 STOP。
- 指标：success@0.5m、success@3m、oracle success、SPL、距离、路径、步数、碰撞和动作计数。
- 基础模型和 LoRA 必须读取相同 RGB/depth/指令；不能用单条成功替代总体指标。

## 唯一指标源

`adapter/evaluate_sidecars.py` 生成的 `eval_result.json` 当前包含两个层次：

1. `controller_validation`：真实采集控制器的接口/数据闭环核验。
2. `base_model` / `lora_model`：明确为 `not_run`，原因是 LoRA 训练 gate 在首 batch 的 logits shape 校验处失败，没有可重载 adapter。

控制器核验（不是 StreamVLN 模型成绩）为：10/10 在 0.5m 内 STOP，10/10 oracle success，平均最终距离 `0.4800000259m`，平均路径 `3.5m`，平均 27 步，碰撞 0，平均 SPL 1.0。

## 证据

- [真实 RGB GIF](../assets/gifs/stage1-smoke-controller.gif)
- [竖屏复盘视频](../assets/videos/stage1-smoke-retrospective-vertical.mp4)
- [机器可读指标源](../experiments/exp01-baseline/eval_result.json)

## 结论

在模型基础/LoRA 评测完成前，不能把控制器结果宣传为“StreamVLN 成功案例”；若后续模型 gate 仍阻塞，公开内容应保持透明的“非官方适配失败复盘”。
