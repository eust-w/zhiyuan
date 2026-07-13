# 03｜Stage 2：让 LoRA 真的发生更新

同学们，训练进程“退出码为 0”并不等于训练有效。本轮第一次运行就遇到一个很典型的陷阱：上游脚本收到不存在的 `qwen` 模板键后静默回退到 Vicuna，动作标签全部被 mask，最后 59 步 loss 和梯度都是 0。我们保留失败证据，并把“非零 loss + 非零梯度”设为硬门。

![Stage 2 四道门](../assets/screenshots/v3/stage2-gates.png)

## 固定训练配置

| 参数 | 本轮值 |
| --- | --- |
| 基座 | StreamVLN real-world，固定 revision `7b0269…` |
| 视觉塔 | SigLIP，固定 revision `9fdffc…` |
| LoRA | `r=8`、`alpha=16`、dropout `0.05` |
| 训练 | 1 epoch、batch 1、LR `2e-5`、BF16 |
| 多模态 | `mm_tunable_parts=mm_lora_layer`、gradient checkpointing |
| 环境 | StreamVLN Python 3.9；Isaac Python 3.11 完全分开 |

## 第一道门：dataset-only

50/50 条训练 episode 在加载模型前先通过严格检查，避免花 GPU 时间训练坏数据。

## 第二道门：单 batch 前后向

正确模板键改为公开代码真实存在的 `qwen_2`；同时用 token 字符串解析 `<|im_start|>` 与 `<|im_end|>`，避免把“额外 special token 数量恰好等于 2”当成前提。独立单批次结果：

```text
loss       = 0.4167
grad_norm  = 0.3836
peak VRAM  ≈ 22.47 GiB
NaN / Inf  = false
```

只有这一步通过，完整训练才会启动。

## 第三道门：完整训练

![59 步 loss 与 grad_norm](../assets/screenshots/v3/stage2-loss-curve.png)

训练证据动图：[stage2-training-evidence.gif](../assets/media/v3/stage2-training-evidence.gif)；1080p/30fps 无声片段：[MP4](../assets/media/v3/stage2-training-evidence.mp4)。

完整训练实际记录 **59 个更新步**，首步 loss `0.4167`，末步 `0.0823`，最大 grad_norm `0.8733`，峰值显存约 `27.19GiB`，没有 OOM、NaN 或 Inf。训练 loss 下降只说明模型拟合了这批数据，不能替代仿真成功率。

## 第四道门：新进程重载

训练结束后另起 Python 3.9 进程，用 PEFT 将 adapter 挂载到基座，重载通过。adapter 文件 SHA-256 为：

```text
7e4a1fbb6b7fa7b23f2a9459db7f02e88c3cb2ae0a23e23d74f1dfdefd8c57c3
```

完整机器结果见 [`stage2_result_v2.json`](../experiments/exp02-equivalent-v3/stage2_result_v2.json)，原始 loss 日志见 [`stage2-train.stdout.log`](../experiments/exp02-equivalent-v3/logs/stage2-train.stdout.log)。权重和 adapter 只保留在持久盘，不提交 Git、不再分发。

## 本阶段结论

Stage 2 的数据门、真实反向传播、完整训练和新进程重载均已完成。真正的质量判断继续交给 Stage 3：同一批 held-out 上 base 与 LoRA 谁更好，由 `eval_result.json` 说话。
