# 07｜对照 PDF：这次到底完成到什么程度？

同学们，判断“做完没有”不能只看有没有一段机器人移动视频，而要逐项对照课程目标、产物和证据。本表以 13 页《GenieSim + VLN 技术开发指南》为准。

| PDF 要求 | 本轮状态 | 证据 / 等价说明 |
| --- | --- | --- |
| 同一场景的 PLY/USDA/USDZ | 等价完成 | 1762 帧 RGB-D 自采 20 万点，三个等价文件同源并在新 Isaac 进程打开；不是课程私有原件 |
| Isaac / GPU / 场景 / 机器人启动 | 完成 | `market_00_g2`、G2、头部 RGB/depth、`ready=true` |
| W/S/A/D/Space | 完成 | Stage 0 debug-only keyboard 真实记录；S 不进入训练动作空间 |
| 障碍前进拒绝 | 等价完成 | 真实 head-depth 近障碍安全门拒绝，位姿不变；不是课程 USD AABB 实现 |
| 50 条训练数据 | 完成 | seeds `1001–1050`，50/50 严格校验 |
| RGB/depth/annotations/target/trajectory | 完成 | 公开 annotations + 完整 `geniesim-streamvln/v1` sidecar |
| 人工抽查 RGB 轨迹 | 完成 | 文档展示多条不同起点/视角，另有 10 秒 GIF 与 1080p MP4 |
| LoRA adapter | 完成 | `r=8/alpha=16/dropout=.05`，1 epoch、59 个非零更新步 |
| loss / grad_norm / 显存 | 完成 | 真实日志、曲线、峰值 27.19GiB，无 NaN/Inf |
| 新进程加载 adapter | 完成 | PEFT 独立进程重载通过，adapter SHA 已记录 |
| 自然语言 → StreamVLN → GenieSim 闭环 | 完成 | base 与 LoRA 都走真实 `generate`，动作回送 loopback GenieSim |
| 同一批 held-out 评测 | 完成 | 固定 `eval-2001…2010`，每条重置模型 cache，最大 200 步 |
| success/oracle/distance/path/steps/actions/collision | 完成 | 唯一来源 `eval_result.json`，包含全部成功与失败 |
| 失败分析和下一轮计划 | 完成 | Stage 4/5 文档与抖音稿按失败复盘呈现 |
| 测试、哈希与关机收尾 | 完成 | 31 项测试通过；5 个关键文件本地/持久盘哈希一致；控制台“已关机”证据已保存 |
| 使用课程私有 `course_tools` 和 UDP | 未完成且不冒充 | 私有软件不可由仿真自采；使用独立等价接口，不提交课程榜单 |

## 如何给这次实验定性

如果“完成课程”被严格定义为逐字执行课程私有脚本和 UDP 协议，这次不能称为原样复现，因为私有文件并不存在于当前附件和镜像。

如果按 PDF 的六个学习目标和 Stage 0–3 产物验收，本轮已经完成一条有真实数据、真实微调、真实模型动作和真实评测的**非官方等价实验闭环**。模型是否成功到达目标，要继续以最终 `eval_result.json` 的 0.5m 成功标准判断；失败并不等于实验没做，伪造成功才是没有完成实验方法。
