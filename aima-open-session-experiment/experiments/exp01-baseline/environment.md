# exp01-baseline 环境清单

采集时间：2026-07-13
状态：Stage 0/1 已真实运行；模型训练与配对评测仍在 gate 阶段。

| 项目 | 值 |
| --- | --- |
| OS | Linux 5.15.0-168-generic x86_64 |
| GPU | NVIDIA L40，46068 MiB |
| NVIDIA driver | 580.126.09 |
| Isaac Sim | 5.1.0-rc.19+release.26219.9c81211b.gl |
| Isaac Python | 3.11.13 |
| Genie Sim commit | a04fe4f7fda0ec6e01ab652fa19094008312bf97 |
| Display | `:20`，1920×1080 |
| 系统盘 | 30GB；实验资产不得写入 |
| 持久盘 | `/root/gpufree-data`，100GB；数据盘实验根目录 |
| 工作区 | `/root/gpufree-data/zhiyuan-aima` |
| SSH | 本机 ED25519 公钥免密验证成功（不记录连接命令） |
| cuRobo | 未安装；镜像内 cp310 wheel 与当前 Python 3.11 不兼容 |

## StreamVLN 独立环境

```text
HF_HOME=/root/gpufree-data/zhiyuan-aima/cache/hf
TORCH_HOME=/root/gpufree-data/zhiyuan-aima/cache/torch
CONDA_PKGS_DIRS=/root/gpufree-data/zhiyuan-aima/cache/conda
/root/.cache/ov -> /root/gpufree-data/zhiyuan-aima/cache/ov
```

`/root/gpufree-data/zhiyuan-aima/cache/conda/streamvln-py39` 使用 Python 3.9；Isaac Sim 仍使用 Python 3.11。HF 权重只写入持久盘 checkpoint 目录，不进入 Git。
