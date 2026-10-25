# 样片事实与分镜契约

## 生成与校验

在仓库根目录执行：

```sh
node documentary/scripts/facts.mjs
node documentary/scripts/facts.mjs --check
node --test documentary/tests/contract.test.mjs
```

第一条从三个原始 JSON 重新生成 `src/generated/facts.json`；第二条逐字比较当前生成物与原始证据。所有计算使用 Node 内置模块，无新增依赖。指标变化会触发检查，不会自动把原来的讲述改成成功结论。

## 画面读取接口

```ts
import facts from './generated/facts.json';
```

| 数据 | 字段 |
| --- | --- |
| 固定评测集合 | `historical.heldoutEpisodeIds` |
| 主成功半径 | `historical.successRadiusM` |
| 模型结果 | `historical.base`、`historical.lora` |
| 成功数量 | `successCount`，分母为 `historical.episodes` |
| 路径效率代理 | `splProxy`，必须展示 `metricSemantics.spl.label` |
| 最终／最近距离 | `meanFinalDistanceM`、`meanMinDistanceM` |
| 前进被安全门拒绝次数 | `blockedForwardCount`，不是物理接触次数 |
| 动作计数 | `actionCounts.stop/forward/left/right` |
| 单条评测 | `episodes[i]`，`id` 为原始固定任务编号 |
| 单条轨迹 | `episodes[i].trajectory` |
| 目标坐标 | `episodes[i].targetXY` |
| 训练首末损失 | `training.lossFirst`、`training.lossLast` |
| 更新步数和峰值显存 | `training.updates`、`training.peakGpuMemoryMiB` |
| 本地迁移验收 | `migration.testsPassed`、`migration.date` |
| 新栈真实导航复测 | `migration.gpuRetested`、`migration.navigationCompared`，均为 `false` |

轨迹点为 `{step, xy: [x, y], headingRad, distanceM, actionId, blocked}`。第零点尚未执行动作，`actionId` 为 `null`；后续点的动作来自已执行的预测队列。截断边界之外、生成但没有执行的动作不会计入轨迹和动作统计。

开场实际绑定 `media/base-2004.mp4`，对应基础模型 `episodes[3]` 的 `eval-2004`。源媒体为 10 秒，仅使用第 0–8 秒，不循环。开场不读取后文配对任务的指标。

配对片段指定 `eval-2001`，即两组 `episodes[0]`，根据 JSON 中的位姿、距离和动作记录重绘轨迹。提取器同时检查任务编号、随机种子、起点、朝向和目标位置一致。它不是原始 RGB 回放：标签为“真实结果图”，说明为“真实轨迹记录重绘；按动作步同步，不代表墙钟时间”。两侧使用同一动作步，较短轨迹结束后停在其实际终点，不循环、不补造动作。

`training.lossSeriesAvailable` 为 `false`：结果 JSON 只提供首末损失。不允许用两点插值冒充逐步训练曲线。训练镜头现已绑定 `media/loss-curve.png`，它是恢复的真实原训练曲线截图，原样使用，不从首末值重建。三个媒体来源的 SHA-256 已核对，并记录在 `media.json`；`scripts/media.mjs --decode` 会验证真实文件字节并完整解码。

## 来源与发布状态

`sample.json` 是 78 秒、30 帧／秒、七段连续镜头的结构契约；每段字幕时间相对该镜头开始。声音尚未合成，字幕时间为编辑计划。

每段 `source` 都有准确类别和中文标签：

- `data_replay`：真实数据回放。
- `result_plot`：真实结果图，绑定已有真实结果素材。
- `diagram`：示意动画。
- `schema_visualization`：数据结构示意。
- `metrics_visualization`：由事实 JSON 驱动的真实结果图。

媒体未绑定时保留 `sourcePending: true`、`mediaPath: null`、`timing: null`。不要填造文件路径、录制时间或哈希。当前开场和训练素材已绑定，配对轨迹改为事实驱动绘图，因此实际样片无待绑定来源；缺源回归测试使用单独构造的测试样本。媒体路径相对 `documentary/public/`，不接受绝对路径、上级目录和外部 URL。

`validateStoryboard(sample, facts)` 返回结构错误列表；空列表只代表结构通过。`publicationGate(sample, facts, {publicRoot})` 返回 `{ready, blockers}`；未完成配音、缺少媒体或最终确认时必须保持 `ready: false`。该门检查文件存在，不替代解码、OCR、许可证、音画对应和人工终审。

`provenance` 仅包含三个原始 JSON 的 SHA-256。生成文件用字段白名单输出，不传播原始命令、环境路径、连接信息或自由文本。
