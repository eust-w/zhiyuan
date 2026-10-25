# 模型依赖迁移：本地 CPU 验证范围

日期：2026-10-25。范围：固定 StreamVLN 源码的 Qwen＋SigLIP＋单设备监督 LoRA 路径。此次没有启动 GPU、下载真实模型权重、修改 Isaac 环境或重跑导航指标。

## 与历史审计的关系

[首次依赖审计](audit-2026-10-25.md) 发现的历史漏洞记录全部保留。新的安装清单不是旧 154 包快照的“忽略漏洞版”，也不修改历史环境：它只包含当前限定功能实际需要的完整依赖图，通过源码隔离解除未使用功能的强制导入。

新的 [model.in](../requirements/model.in) 固定核心版本：

| 组件 | 新版本 |
| --- | --- |
| Python | 本地验证 3.12.14；锁文件面向 3.12 |
| PyTorch / torchvision | 2.14.1 / 0.29.1；Linux CPU wheel 带 `+cpu` 后缀 |
| Transformers / tokenizers | 5.20.2 / 0.23.3 |
| PEFT / Accelerate | 0.21.2 / 1.15.0 |
| safetensors | 0.8.0 |
| NumPy / Pillow | 2.5.4 / 13.0.0 |

完整版本与下载哈希见 [macOS ARM64 锁](../requirements/model-macos-arm64.txt) 和 [Linux x86_64 CPU 锁](../requirements/model-linux-cpu.txt)，各 44 个分发包。macOS 要求 14 或更新版本以使用该 PyTorch wheel。

## 审计方法与结果

| 清单 | 漏洞源 | 包数 | 审计结果 |
| --- | --- | ---: | --- |
| macOS ARM64 模型锁 | PyPI / pip-audit 2.10.1 | 44 | 未报告已知漏洞 |
| Linux CPU 模型锁 | OSV / pip-audit 2.10.1 | 44 | 未报告已知漏洞 |

原始结果：[macOS JSON](evidence/model-macos-arm64-audit.json)、[Linux CPU OSV JSON](evidence/model-linux-cpu-osv-audit.json)。这是指定漏洞数据库在审计时点的结果，不是不存在未知漏洞的保证。

PyPI 的版本元数据端点不能识别 `torch==2.14.1+cpu`，直接 PyPI 审计确实失败，未将该失败忽略。Linux 改用 OSV 全图查询，保留原始 `+cpu` 版本号；用已知受影响的 `torch==2.1.2+cpu` 作查询对照时，OSV 返回 28 条公告记录，说明没有静默跳过这类版本。

OSV 模式的 `--require-hashes` 只检查哈希是否存在，不能验证哈希真实性。因此安装必须另用 `pip install --require-hashes` 或 `uv pip sync --require-hashes` 实际验证下载文件，之后运行 `pip check`。不使用 CVE 忽略清单、`continue-on-error` 或 `|| true`。查询故障算失败，重试成功后才记录通过。

此外手工复核了包名被记录为 `pytorch` 而非 `torch` 的 [GHSA-63cw-57p8-fm3p](https://github.com/advisories/GHSA-63cw-57p8-fm3p)：公告修复版本为 2.10.0，新版本 2.14.1 高于该修复点。名称不匹配的公告不能仅依赖按 `torch` 查询覆盖。

## 兼容修改

固定源码 revision 仍为 `e48f6ff7e9201d93aae003e8f64b04c00cec13bc`。三个现有入口在本地权重安全检查后调用 [streamvln_compat.py](../aima-open-session-experiment/adapter/streamvln_compat.py)。它先验证 revision、作用域内 Python 源码、补丁及前后 SHA-256，再应用可重复的补丁。未知修改或路径越界会阻止继续；不是任意版本通用补丁，也不是 Python 沙箱。

- 显式处理 Transformers 5 的 chat-template 返回结构与 special-token ID。
- 统一从本地 JSON 读取真实 checkpoint 的旧式平铺 Qwen 配置。其 `model_type=llava` 与嵌套默认 Llama 配置不能用于自动选择架构；保留顶层 Qwen 尺寸和词表，不裁剪原始权重。训练、重载和评测使用同一加载函数。
- 迁移 SigLIP 配置读取、模型加载与生成 cache 契约，保留多模态特征语义。
- 将原监督 Trainer 接到受维护的 Transformers Trainer 接口，验证损失归一化和保存行为。
- GPU 训练路径仍要求 BF16；仅显式传入 `--use_cpu True` 的本地验证可使用 FP32，不因 CUDA 不可用而静默回退。
- 非 SigLIP 视觉塔、非空重采样器、DPO、分布式训练、ZeRO 和特殊分组/学习率模式不属于新 profile；不能把这些功能的旧依赖删除后称为已经迁移。
- 保留 safetensors-only、本地路径检查、离线加载，以及未知输出安全 STOP。
- GenieSim HTTP API、动作编号、数据格式、held-out ID 和 0.5m 主成功半径不变。

补丁与源文件清单：[manifest.json](../aima-open-session-experiment/adapter/compat_assets/manifest.json)。改编片段继续遵守 [第三方许可声明](../THIRD_PARTY_NOTICES.md)，不统一改授 MIT。

### 发现的历史视觉参数丢失问题

独立复核发现，旧入口在 `mm_lora_layer` 模式下延迟创建视觉塔，导致基座内的视觉参数在首次加载时被忽略，之后仅使用外部 SigLIP 参数。固定真实 checkpoint 的公开索引含 421 个视觉参数；本地小模型将基座视觉参数修改后保存，重载确实丢失修改，最大绝对差为 1.0。

新流程保持先附加语言 LoRA、后创建视觉塔的顺序，再从基座 safetensors 恢复嵌入的视觉参数，防止视觉层被意外加入 LoRA。该修复不是纯 API 替换：新运行可能产生不同输出。历史 0/10 不重写，也不能作为新版数值或轨迹等价证明；真实权重与闭环仍需独立复测。

恢复器仅提取视觉 tensor；索引与分片路径、完整参数集合、重复条目和形状均需通过检查，缺失或部分视觉权重不会静默回退。日志中的初次延迟加载仍可能显示视觉 `UNEXPECTED` 项，随后必须出现明确的 `restored` 记录；不能只凭首次加载结束判断整模型恢复成功。小模型测试另对修改后的视觉参数逐项比对，并确认语言 LoRA 没有扩展到视觉层。

### Linux CI 暴露的非持久位置索引问题

第二次 [Linux CI 运行](https://github.com/eust-w/zhiyuan/actions/runs/40190094395) 已完成哈希锁安装及漏洞审计，但模型测试暴露了 SigLIP 的位置索引越界。Transformers 5 在 meta 加载后使用 `empty_like` 重建非持久 buffer；固定上游的 `_init_weights` 为空，未将 `position_ids` 恢复为准确的网格序列。本地先前偶然通过不能证明初始化正确。

修复遵循 Transformers 的初始化钩子，仅重建 `0…N-1` 的位置索引，不截断索引、不改变网格，也不修改已加载参数。新增测试使用 PyTorch 的确定性未初始化内存填充，稳定复现旧实现错误，并验证修复后的索引值、类型、设备、非持久属性及所有已加载视觉参数逐 tensor 不变。视觉塔加载、完整基座恢复和新进程 LoRA 重载均执行精确索引断言。

同次 CI 还发现测试夹具的本地 clone 无法处理浅克隆＋partial checkout，会尝试抓取被排除的媒体对象。夹具改为独立 detached worktree，只物化 Python 源码；回归用例禁用缺失对象下载，验证父 checkout 的 HEAD、文件、sparse 选择不变，且清理仅删除本项测试创建的 worktree。没有跳过源码安全守卫或下载媒体来绕过失败。

## 本地复查

所有命令从仓库根目录执行。模型、媒体、审计器分别使用独立环境；不要安装到 Isaac 的 Python 中。

### 安装与审计

```bash
python3.12 -m venv .venv-audit
.venv-audit/bin/python -m pip install --require-hashes -r requirements/audit.txt
.venv-audit/bin/pip-audit --strict --disable-pip --require-hashes -r requirements/model-macos-arm64.txt
.venv-audit/bin/pip-audit --strict --disable-pip --require-hashes --vulnerability-service osv -r requirements/model-linux-cpu.txt

python3.12 -m venv .venv-model
# Linux x86_64：只装 CPU wheel，不下载 CUDA runtime。
.venv-model/bin/python -m pip install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu -r requirements/model-linux-cpu.txt
.venv-model/bin/python -m pip check
```

macOS ARM64 用下面一条替代 Linux 安装命令：

```bash
.venv-model/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements/model-macos-arm64.txt
```

### 固定源码与真实小模型测试

```bash
git clone --filter=blob:none --no-checkout https://github.com/InternRobotics/StreamVLN.git .upstream/StreamVLN
git -C .upstream/StreamVLN sparse-checkout set llava streamvln
git -C .upstream/StreamVLN checkout --detach e48f6ff7e9201d93aae003e8f64b04c00cec13bc
export STREAMVLN_REPO="$PWD/.upstream/StreamVLN"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export CUDA_VISIBLE_DEVICES='' ACCELERATE_USE_CPU=true
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false
cd aima-open-session-experiment
../.venv-model/bin/python -m unittest tests.test_streamvln_compat tests.test_model_stack_integration -v
```

测试使用实际 StreamVLN 类、实际 Qwen/SigLIP 运算和随机初始化的小权重，不请求预训练权重。包括与历史 checkpoint 相同的旧配置结构、真实数据集预处理、原训练 CLI 单步 LoRA、checkpoint/最终 adapter 保存及新进程重载。它能验证接口、梯度、生成和序列化行为，不能证明原始 checkpoint 权重可完整加载或机器人任务成功。

源码必须使用独立可信副本。旧 4.x 运行时补丁或手工改动过的 checkout 会被拒绝；请重新检出固定原版，不要强行跳过 hash 检查。运行期间不要让其他进程改动源码或模型目录。

### 重新生成锁文件

锁文件由 uv 0.12.6 生成，输入与命令可复核。维护者更新依赖后必须重新安装、审计并测试。

```bash
MACOSX_DEPLOYMENT_TARGET=14.0 uv pip compile requirements/model.in --python-version 3.12 --python-platform aarch64-apple-darwin --generate-hashes --only-binary :all: --output-file requirements/model-macos-arm64.txt
uv pip compile requirements/model.in --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --torch-backend cpu --generate-hashes --only-binary :all: --output-file requirements/model-linux-cpu.txt
```

Linux 锁不输出索引指令；安装命令显式提供 PyPI 和 PyTorch CPU 两个索引。首次 [CI 运行](https://github.com/eust-w/zhiyuan/actions/runs/40189596695) 在安装时发现：锁内的单独 `--index-url` 会重置 pip 索引列表，清掉命令行的 CPU extra index，因而找不到 `torch==2.14.1+cpu`。已按 [pip 的全局选项规则](https://pip.pypa.io/en/stable/reference/requirements-file-format/#global-options)及实际解析行为复核，并重新生成不含该覆盖项的锁；44 个包、版本和所有分发哈希均不变。没有通过删除 `+cpu`、放松哈希或忽略安装失败来规避问题。

## 本次本地验收

机器可读证据及输入哈希见 [model-migration-verification.json](evidence/model-migration-verification.json)。

- macOS ARM64 / Python 3.12.14：模型锁实际按哈希安装成功，模型、媒体和审计器三个独立环境的 `pip check` 均通过。
- **106 项**相关 CPU 回归、**10 项**固定源码保护与浅克隆夹具测试、**16 项**真实小模型集成测试通过，无失败或跳过。CI 使用相同模块清单。
- 完成多模态 FP32/CPU BF16 前后向、8 帧历史与独立 reset、多 token 生成、梯度累积归一化、原训练 CLI 单步 LoRA、checkpoint 与最终 adapter 导出，以及新进程重载比对。
- 真实 checkpoint 的配置 JSON 和少量 safetensors 头信息只用于结构复核；meta 构建保持 `152064×3584` 的词表/head 尺寸，不是完整权重加载验证。
- 视觉保值回归覆盖修改后的嵌入参数与 logits、分片恢复、语言 LoRA 隔离，以及 7 类错误布局/索引/路径/形状拒绝。
- 三个项目入口 `--help`、Python 编译检查、差异格式检查和变更范围 Gitleaks 扫描通过。模型锁与既有 CPU/审计器锁最终扫描均通过，无公告忽略项。
- 上游可选视频解码依赖及弃用提示仍可能出现；本 profile 不包含那些功能。初次延迟视觉加载的提示按前述恢复记录解释，不隐藏日志或把未执行的功能算作通过。

Linux CPU 的哈希安装与同组测试交给独立 GitHub Actions job；须核对相应提交的实际运行结果。本地验收记录不冒充远端 CI 或 GPU 验收。

## 明确未验证的部分

- CUDA wheel 变体、NVIDIA 驱动、BF16/SDPA GPU 内核、显存与实际性能；Linux CPU 锁不能用作 GPU 安装锁。
- 固定真实 checkpoint、原始 tokenizer 文件、原始训练样本与历史 LoRA 权重在新栈中的加载和数值一致性。
- GenieSim 真实场景的模型闭环，以及同批 10＋10 条新版配对评测。
- Isaac/Kit、系统 CUDA、媒体工具及 wheel 内原生库的独立供应链审计。

历史 Base/LoRA 0/10、loss、显存和轨迹 JSON 原样保留，**不作为新栈验收结果**。用户本轮明确要求不启动 GPU；以后只有获得预算授权、确认资产可恢复与当前驱动后，才能开始 GPU 复测。
