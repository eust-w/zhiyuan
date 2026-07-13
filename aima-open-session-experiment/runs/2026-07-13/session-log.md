# GenieSim × StreamVLN 非官方等价实验运行日志

> 教学提示：这份日志区分“控制器能走”“训练真的更新”“模型自己闭环”三件事。流程参考 AIMA 指南，但未使用课程私有适配包，也不提交课程榜单。

## 环境与边界

- GPUFree L40 48GB、100GB 持久盘、SSH 公钥认证、Isaac Sim 5.1 与预装 Genie Sim 3.0 已验证。
- 场景为 `market_00_g2`，机器人采用 G2 刚体导航代理与头部 RGB/depth；不宣称真实人形步态。
- 服务只监听本机回环地址，HTTP 线程排队，所有 Isaac 操作回到主线程执行。
- 课程私有 adapter、`course_tools` 与 UDP 协议不可得；本轮实现独立、可审计的等价接口。

## Stage 0｜先证明动作与安全门可靠

- W/S/A/D/Space 五个按键全部留下 debug-only 记录；后退不进入训练动作空间。
- 一次清晰前进的位移为 0.25m；转向增量为 15°。
- 头部深度图中央区域第 10 百分位小于 0.45m 时，危险前进被拒绝，位姿保持不变。
- RGB、depth、4×4 pose、目标距离和 blocked 状态均可写盘。

## Stage 1｜自采等价数据与三维文件

- 3 条冒烟、50 条训练（seeds 1001–1050）、10 条留出评测（2001–2010）完成。
- train 50/50、eval 10/10 通过 schema、帧数、动作数、路径与图像解码校验。
- 公开 RGB 共 1699 帧，无全黑帧；50 条训练轨迹有 50 个不同起点。
- 1762 帧带标定 RGB-D 合成 20 万点点云，并导出同源 PLY、USDA、USDZ；USDA 与 USDZ 均在新 Isaac 进程验证默认 Prim 与点集。
- 公开标注首动作是 -1、不写最终 STOP；depth、完整动作、位姿、碰撞和目标信息写入 `geniesim-streamvln/v1` sidecar。

## Stage 2｜确认训练不是“假通过”

- 发现上游 `--version qwen` 不存在并静默回退到 Vicuna 模板，导致标签全部被 mask、旧训练出现假 0-loss。
- 改为真实模板键 `qwen_2`，特殊 token 用 tokenizer ID 解析，并将词表与 `lm_head` 输出对齐。
- 单批前后向：loss 0.4167、grad norm 0.3836、峰值显存 23008MiB。
- 完整训练：59 个非零更新步，loss 0.4167→0.0823，最大 grad norm 0.8733353，峰值显存 27846MiB，无 NaN/Inf。
- adapter 在新进程重载通过；最终 SHA-256 为 `7e4a1fbb6b7fa7b23f2a9459db7f02e88c3cb2ae0a23e23d74f1dfdefd8c57c3`。

## Stage 3｜同一批 10 条的真实模型闭环

- 基础模型与 LoRA 都读取观测并调用模型 `generate`，离散动作再送回 GenieSim；不是 A* 控制器代跑。
- 两组严格使用 `eval-2001…2010`，每条重置 cache、动作队列和历史记忆，最大 200 步。
- 基础模型：success@0.5m 0/10，success@3m 2/10，oracle@3m 3/10，SPL@3m 0.07484，平均最终距离 3.989m，平均路径 9.675m，平均 133.9 步，安全门拦截 132 次。
- LoRA：success@0.5m 0/10，success@3m 1/10，oracle@3m 1/10，SPL@3m 0.06646，平均最终距离 4.686m，平均路径 5.5m，平均 53.2 步，安全门拦截 45 次。
- 唯一指标源为 `experiments/exp02-equivalent-v3/eval_result.json`；全部成功与失败 episode 都进入汇总。

## 内容与定性

- 每阶段至少两张截图和一段 GIF/MP4；最终轮播 20 张，竖屏成片 1080×1920、30fps、H.264、55 秒，配沉稳男声 AAC 音轨。
- 本轮对学习目标可称“非官方等价实验闭环完成”，对课程私有脚本与协议不能称“原样复现”。
- 模型在 0.5m 标准下没有成功，因此公开稿统一使用“透明失败复盘”，绝不把控制器轨迹包装成模型成绩。

## 收尾（2026-07-14）

- 本地执行 31 项单元测试，全部通过；`compileall` 与 `git diff --check` 通过。
- 最终 GIF 全部多于 1 帧，所有 GIF/MP4 完整解码通过；竖屏成片为 1080×1920、30fps、H.264、55 秒，AAC 音轨为 `zh-CN-YunyangNeural` 沉稳男声。
- Markdown 内部链接无断链；公开交付扫描未发现邮箱、凭据赋值或非回环 IP。
- 本地与持久盘的唯一指标源、PLY、USDA、USDZ、55 秒有声成片共 5 个 SHA-256 全部一致；旁车音频文案、MP3 与 SRT 也已纳入最终 manifest。
- 云端训练、评测、适配器和 GPU compute 进程均为 0；GPUFree 控制台显示“已关机”，裁剪后的无敏感信息证据见 `assets/screenshots/v3/final-instance-powered-off.jpg`。
