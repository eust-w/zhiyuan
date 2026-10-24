# GenieSim × StreamVLN 控制与评测适配器

[项目首页](../../README.md) · [实验索引](../README.md) · [许可边界](../../THIRD_PARTY_NOTICES.md)

本目录连接模型动作、仿真观测、数据记录和评测。它不是人形步态控制器，也不提供模型权重或完整场景安装包。

## 进程与运行约束

- 仿真进程使用 Isaac Sim 自带 Python；历史 GPUFree 路径为 `/isaac-sim/python.sh`。
- StreamVLN / PEFT 使用独立模型环境；历史实验为 Python 3.9。不要混装两个环境。
- HTTP 服务只监听 `127.0.0.1:5802`。HTTP 线程提交请求，主线程执行 Isaac/USD 操作；动作后等待渲染再记录观测。
- 实验根目录需要可写，RGB、depth、pose 与 sidecar 写入该目录。文件路径必须仍处于实验根目录内。
- `stage2_preflight` 会对传入的 StreamVLN checkout 应用兼容补丁；请使用独立副本并保存上游 revision。该模块中的上游片段另有许可，见仓库根目录第三方声明。

## 动作空间

| ID | 动作 |
| --- | --- |
| `0` | STOP |
| `1` | 前进 0.25m |
| `2` | 左转 15° |
| `3` | 右转 15° |

键盘后退仅用于人工验证，不属于训练或模型输出动作空间。这里的导航采用刚体位姿变化，不表示机器人生成了真实行走步态。

## HTTP 接口

| 方法与路径 | 用途 |
| --- | --- |
| `GET /health` | 检查场景、相机、导航与写入状态 |
| `POST /v1/episodes/reset` | 重置 episode，传入 schema、ID、seed、instruction、target_id |
| `POST /v1/episodes/{id}/step` | 提交 `request_id` 和 `action_id`；重复请求不重复执行动作 |
| `POST /v1/episodes/{id}/close` | 结束 episode 并刷新记录 |

观测响应包含 step、相对 RGB/depth 路径、4×4 pose、目标距离、`blocked`、`terminated` 和 `truncated`。具体字段及校验以 [protocol.py](protocol.py) 与 [service.py](service.py) 为准。接口无公网认证层，不要将端口直接开放给外部网络。

## 从哪里开始

在本目录的上一级（`aima-open-session-experiment`）运行模块。普通 CPU 的最小测试命令见[项目首页](../../README.md#快速检查无需-gpu)。完整 GPU 运行前必须自行准备依赖、模型和场景；以下只列入口，不表示裸 clone 即可运行：

| 入口 | 说明 |
| --- | --- |
| `python3 -m adapter.vln_app --help` | 仿真启动参数；实际启动须用 Isaac Python |
| `python3 -m adapter.collect_dataset --help` | 控制器采集参数 |
| `python3 -m adapter.stage2_preflight --help` | 训练检查参数；执行前核实第三方许可和副本路径 |
| `python3 -m adapter.model_closed_loop_eval --help` | 真正模型闭环入口；需要模型环境 |
| `python3 -m adapter.evaluate_sidecars --help` | 控制器轨迹汇总，不能用作模型成绩 |

默认配置见 [nonofficial-market-g2.yaml](../configs/nonofficial-market-g2.yaml)。历史 shell 启动器还有 `/isaac-sim` 等平台路径假设，换机器时须逐项核对。

## 安全门、栅格与历史结果的区别

历史配对模型评测的 health 为 `occupancy_source=runtime_safe_fallback_no_usd_aabb`、`forward_safety=head_depth_center_p10_lt_0.45m`。因此其 `collisions` 表示深度安全门拦截，不是物理接触碰撞。

独立 `market-aabb-proxy.usda` 含 10 个 Cube，已验证 5cm 栅格投影及 footprint + 5cm 膨胀；但预装视觉市场 mesh 对完整 HTTP/Kit 进程的提前退出问题仍保留。独立代理层探针、配置开关和历史深度安全门评测是不同证据，不能合并描述为完整视觉 AABB 闭环已经稳定通过。

当前 [metrics.py](metrics.py) 的最短路使用初始直线距离代理，因此 SPL 不能直接与 geodesic SPL 基准比较。数据检查中的非空图像检查也不能代替实际解码。

## RGB-D 场景衍生物

`adapter.equivalent_assets` 可使用带相机标定的观测生成 PLY、点云型 USDA、USDZ 和哈希清单；无限 depth fallback 帧会被拒绝。格式转换或从仿真重新采样，不自动授予上游场景的再分发权。此类资产不适用本项目代码的 MIT 许可，使用前请核实来源与授权。
