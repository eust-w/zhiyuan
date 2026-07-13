# 2026-07-13 实验日志

## 环境与安全

- GPUFree L40 48GB、100GB 持久盘、SSH 公钥认证、Isaac Sim 5.1 与 Genie Sim 3.0 已验证。
- 公开课程私有 adapter/`course_tools` 未找到；本实验全程标注为非官方个人适配，不提交 AgiBot Open Session 榜单。
- 运行根目录、模型、数据和媒体均在持久盘；公开仓库不保存 IP、实例 ID、连接信息或凭据。

## Stage 0

- 启动 `market_00_g2` + G2 Omnipicker + 头部相机。
- `/health`、`reset`、`step`、重复 request_id 幂等、`close` 均真实验证。
- RGB 640×400、depth NPY、pose 和目标距离均有效。
- USD AABB 遍历触发 SimulationApp clean shutdown；配置记录 `runtime_safe_fallback_no_usd_aabb`，没有伪造障碍结果。

## Stage 1

- 3 条冒烟、50 条训练（1001–1050）、10 条评测（2001–2010）均已采集。
- train annotation：50/50 通过；eval annotation：10/10 通过。
- 每条轨迹包含完整 sidecar（STOP、depth、pose、碰撞、目标），公开动作数组不写最终 STOP。
- 控制器闭环核验：10/10 在 0.5m 内停止，平均最终距离 0.4800000259m，碰撞 0，平均 27 步。

## StreamVLN

- 代码、real-world checkpoint、SigLIP 的 pinned revision 已核验。
- GPUFree 直连 Hugging Face 超时，切换 `hf-mirror.com` 成功下载 checkpoint 与 SigLIP 到持久盘。
- Python 3.9 环境、Transformers 4.45.1 和 StreamVLN 依赖已验证；4 个 checkpoint 分片加载成功。
- LoRA 训练首 batch 失败：`RuntimeError: shape '[-1, 152064]' is invalid for input of size 241878560`；无 OOM、无 adapter，adapter reload 与 base/LoRA 推理均 `not_run`。
- `eval_result.json` 将模型 base/LoRA 明确标为 `not_run`，控制器数字不作为模型成绩；详见 `stage2_result.json` 和 `stage2-failure.log`。

## 媒体

- 真实 RGB 帧已脱离运行目录保存为截图。
- 5 帧 GIF：960×540、5 帧、10fps 播放节奏。
- 竖屏 MP4：1080×1920、30fps、H.264、无音轨、54 秒；烧录非官方与 fallback 限制字幕。
