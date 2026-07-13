# 03｜Stage 2：StreamVLN LoRA 微调

状态：数据 gate 已通过；公开权重已按 pinned revision 下载到持久盘；Python 3.9 依赖和 4 个 checkpoint 分片加载成功，但首个训练 batch 在 logits shape 校验处失败，没有生成 adapter。

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
2. 单 batch 前向/反向：随完整训练首 batch 执行，失败并保留精确异常。
3. 完整训练：官方 StreamVLN 入口已启动并加载 4 个分片，首 batch 失败，退出码 1；没有 OOM。
4. adapter 重载：`not_run`，因为失败发生在 adapter 写入前。

命令由 `adapter/stage2_preflight.py` 生成并保存为 `train-command.txt`；任何 gate 失败都会写入 `stage2_result.json` 的 `blocked/failed` 状态，不生成伪 adapter。

## 许可边界

StreamVLN 仓库与 checkpoint 的公开页面未给出适用于本实验的明确许可证结论；本项目仅作个人非商业研究演示，权重和 adapter 保持在持久盘，不进入 Git 或公开素材。

## 当前结论

首 batch 的真实错误为：`RuntimeError: shape '[-1, 152064]' is invalid for input of size 241878560`。因此 loss、adapter 哈希和模型成功率均不可用；控制器的 10 条评测数字不得写入本节作为模型成绩。下一轮需固定 StreamVLN 与 Transformers 的 tokenizer/多模态 label 对齐版本，再重试。
