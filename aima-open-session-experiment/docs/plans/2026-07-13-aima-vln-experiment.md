# AIMA GenieSim + StreamVLN Experiment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 GPUFree 的 NVIDIA L40 实例上完成 PDF 描述的 GenieSim + StreamVLN Stage 0～3 实验，并交付可复现的图文、动图、视频、评测结果和抖音布道文章。

**Architecture:** GPUFree 实例负责 GPU 仿真、数据采集、LoRA 训练、实时推理与原始取证；`/root/gpufree-data/zhiyuan-aima` 保存可跨关机持久化的工作目录。每个阶段结束即将脱敏后的日志、截图和媒体同步到本地 `aima-open-session-experiment/`，Markdown 仅引用仓库内相对路径。

**Tech Stack:** Genie Sim 3.0、Isaac Sim、ROS 2、StreamVLN、PyTorch/CUDA、SSH/rsync、ffmpeg、Markdown。

---

### Task 1: 建立持久化与取证目录

**Files:**

- Create: `/root/gpufree-data/zhiyuan-aima/{workspace,evidence,logs,checkpoints,runs}`
- Create: `aima-open-session-experiment/runs/2026-07-13/session-log.md`

**Steps:**

1. 用 SSH 验证 L40、驱动、Isaac Sim、根分区和数据盘。
2. 在数据盘创建实验目录；将 Hugging Face、Torch、Conda 和 Isaac 缓存指向数据盘。
3. 检查远程桌面与 `DISPLAY`；确认可用的录屏/截图工具。
4. 保存脱敏环境清单，并立即 rsync 回本地。

**Acceptance:** SSH 公钥免密登录成功；GPU、Isaac Sim 和持久化目录存在；敏感连接信息未进入仓库。

### Task 2: 补齐 PDF 专用课程资产

**Files:**

- Required remote paths: `/root/genie_sim/StreamVLN`, `/root/genie_sim/course_tools`
- Required scene files: `sample.ply`, `sample.usda`, `sample.usdz`
- Required references: `stage0.md`, `stage1.md`, `stage2.md`, `stage3.md`

**Steps:**

1. 搜索镜像、本机下载目录和课程附件中的上述资产。
2. 若课程资产可取得，将其复制到数据盘工作副本，保留原始校验值。
3. 若只能取得官方仓库，先验证 PDF 中定制脚本是否公开；不得伪造同名脚本或结果。
4. 记录所有版本、Git commit、权重来源和许可证。

**Acceptance:** PDF 每条命令对应的真实文件均存在，或明确记录不可取得的课程专有依赖与替代方案。

### Task 3: Stage 0 仿真环境验证

**Files:**

- Evidence: `assets/screenshots/stage0-*`, `assets/videos/stage0-*`, `assets/gifs/stage0-*`
- Report: `docs/01-stage0-仿真环境验证.md`

**Steps:**

1. 运行 `nvidia-smi`、`test -x /isaac-sim/python.sh` 和 `echo $DISPLAY`。
2. 按课程配置启动 `scripts/vln_app.py`，保存完整日志。
3. 另开终端启动 `scripts/keyboard_control.py`。
4. 录制前进、后退、左右转、停止和碰撞阻挡；截取第一/第三视角关键帧。
5. 停止进程并验证本实验没有创建课程未知的 UDP 监听器；适配器只绑定 loopback HTTP `127.0.0.1:5802`。

**Acceptance:** 仿真场景与机器人真实加载，五种键盘动作可验证，视频/GIF 与日志相互对应。

### Task 4: Stage 1 数据采集

**Files:**

- Dataset: `/root/gpufree-data/zhiyuan-aima/workspace/data/course/<scene>_<target>`
- Report: `docs/02-stage1-数据采集.md`

**Steps:**

1. 在可视化工具中选择起点区域和真实目标停靠点。
2. 先采集 3～5 条冒烟样本，人工检查路径、RGB、depth 和指令一致性。
3. 修正明显问题后采集 PDF baseline 的 50 episodes。
4. 运行数据集检查脚本并保存目录树、校验结果和抽样三联图。
5. 将一条 RGB 序列合成为 GIF，并保存采集交互录屏。

**Acceptance:** `annotations.json`、`target.json`、轨迹和 RGB/depth 产物真实存在，检查脚本返回兼容，人工抽检记录完整。

### Task 5: Stage 2 StreamVLN LoRA 微调

**Files:**

- Checkpoints: `/root/gpufree-data/zhiyuan-aima/checkpoints/exp01-baseline`
- Report: `docs/03-stage2-lora微调.md`

**Steps:**

1. 验证基础模型、SigLIP 视觉塔和数据集路径。
2. 使用 PDF baseline：LoRA `r=8`、`alpha=16`、1 epoch、batch size 1；其余参数以 `stage2.md` 为准。
3. 通过 `tmux` 运行训练，持续记录 loss、grad_norm、显存和异常。
4. 绘制 loss 曲线并检查 adapter 必需文件完整性。
5. 保存参数表、日志片段、曲线和权重校验值。

**Acceptance:** adapter 可被重新加载；训练无 NaN/OOM；日志、曲线和权重文件一致。

### Task 6: Stage 3 实时推理与评测

**Files:**

- Runs: `/root/gpufree-data/zhiyuan-aima/runs/exp01-baseline`
- Report: `docs/04-stage3-实时推理评测.md`

**Steps:**

1. 重新启动 VLN 仿真端并确认 loopback HTTP `/health`、`/v1/episodes/*` 可用；不宣称课程 UDP API 兼容。
2. 加载基础模型、LoRA adapter、视觉塔和 `target.json`。
3. 使用包含真实目标名称的指令运行闭环推理并保存每步图像。
4. 保存完整导航视频、动作标注 GIF、轨迹图和 `eval_result.json`。
5. 至少再测试一个起点或指令变体，避免以单次偶然结果作为结论。

**Acceptance:** `success`、距离、步数和动作计数均来自真实评测；成功或代表性失败均有完整视觉证据。

### Task 7: 内容交付与算力收尾

**Files:**

- Reports: `docs/00-*`～`docs/05-*`
- Article: `article/抖音-智元布道师图文稿.md`

**Steps:**

1. 对所有截图和视频执行敏感信息检查与打码。
2. 在每篇 Markdown 中写明目的、命令、现象、产物、结论和下一步，并嵌入相对路径媒体。
3. 生成面向非技术受众的抖音文章、标题、封面文案、配图顺序、动图位置、口播和话题标签。
4. 验证所有相对链接、GIF 可播放、视频可打开、JSON 可解析。
5. 将数据盘关键产物 rsync 回本地，核对校验值；确认无后台任务后关机停止计费。

**Acceptance:** 本地交付可离线阅读，媒体链接无断链，实验结果无占位或伪造内容，GPUFree 实例处于关机状态。
