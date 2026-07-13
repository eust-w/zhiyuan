# 03｜Stage 2：StreamVLN LoRA 微调

状态：四道 Stage 2 gate 已完成；数据 gate、首 batch 前向/反向、50 步 LoRA 训练和新进程 adapter 重载均通过。训练 loss 按实际日志记录为 `0.0`，不把它解释为模型质量结论。

## 固定配置

| 参数 | 值 |
| --- | --- |
| checkpoint | StreamVLN real-world revision `7b0269…` |
| SigLIP | `9fdffc…` |
| LoRA | `r=8`、`alpha=16`、dropout `0.05` |
| 训练 | 1 epoch、batch 1、gradient accumulation 1、LR `2e-5` |
| 精度 | BF16；只有保留 OOM 证据后才允许 4-bit |
| multimodal | `mm_tunable_parts=mm_lora_layer` |
| 运行环境 | 独立 Python 3.9；Isaac Sim 保持 Python 3.11 |

## 四道 gate

1. dataset-only：`train/annotations.json` 严格校验 50/50 已通过。
2. 单 batch 前向/反向：随完整训练首 batch 执行，通过。
3. 完整训练：公开 StreamVLN 入口加载 4 个分片，50/50 步完成，退出码 0；没有 OOM 或 NaN。
4. adapter 重载：独立 Python 3.9 进程加载同一基座并用 PEFT 挂载 LoRA，通过；adapter SHA-256 已写入 `stage2_result.json`。

命令由 `adapter/stage2_preflight.py` 生成并保存为 `train-command.txt`；任何 gate 失败都会写入 `stage2_result.json` 的 `blocked/failed` 状态，不生成伪 adapter。

## 许可边界

StreamVLN 代码仓库 README 标注 CC BY-NC-SA 4.0；checkpoint 的独立授权/再分发条款未在本实验中确认。项目仅作个人非商业研究演示，权重和 adapter 保持在持久盘，不进入 Git 或公开素材。参考：[StreamVLN 官方仓库](https://github.com/InternRobotics/StreamVLN)。

## 当前结论

首次重跑曾观察到 `RuntimeError: shape '[-1, 152064]' is invalid for input of size 241878560`；根因是视觉 token resize 后 `lm_head.out_features=151648` 而旧 config 仍为 `152064`。兼容层在 `initialize_vision_tokenizer` 后对齐词表后，训练和重载均通过。`eval_result.json` 仍不写入模型成功率，因为公开 Habitat evaluator 与 GenieSim sidecar 尚未完成可比的闭环适配。
