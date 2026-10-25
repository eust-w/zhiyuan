# 许可范围与第三方声明

核验日期：2026-10-25。本文区分本项目的授权与外部组件的授权，不代表对整个运行环境、历史素材或完整分发包的法律审计。

## 本项目的 MIT 许可范围

根目录 [LICENSE](LICENSE) 采用标准 MIT License，适用于本项目作者拥有权利的原创源代码、测试、配置及原创文字文档。复用这些内容时须保留版权声明和许可文本。以下第三方内容与明确排除项不因位于本仓库而获得 MIT 授权。

历史记录中的“非商业研究演示”描述当时实验的用途，不给上述原创软件的 MIT 许可增加非商业限制；第三方组件自身的非商业等条件仍须遵守。**本项目原创代码允许的用途，不等于整个模型、资产和媒体组合都允许该用途。**

## 已知的第三方源码片段

文件：[`aima-open-session-experiment/adapter/stage2_preflight.py`](aima-open-session-experiment/adapter/stage2_preflight.py)，函数 `_patch_qwen_tokenizer()`。

该函数的原创包装、检查与调度逻辑采用 MIT；用于匹配及修改上游代码的源码片段，以及由此生成的修改后上游文件，保留各自适用的上游许可，不按本项目 MIT 重新授权。复制整个文件时应一并保留本声明及相关许可文本。

来源版本固定为 StreamVLN `e48f6ff7e9201d93aae003e8f64b04c00cec13bc`：

| 来源 | 本项目涉及的内容 | 保留的许可与归属 |
| --- | --- | --- |
| [streamvln/streamvln_train.py](https://github.com/InternRobotics/StreamVLN/blob/e48f6ff7e9201d93aae003e8f64b04c00cec13bc/streamvln/streamvln_train.py) | tokenizer 调用、special-token 处理、预处理分派、模型词表对齐的匹配/修改片段 | 该文件头的 Apache-2.0 声明及 FastChat / Stanford Alpaca 归属；StreamVLN 贡献另见其仓库声明 |
| [streamvln/dataset/vln_action_dataset.py](https://github.com/InternRobotics/StreamVLN/blob/e48f6ff7e9201d93aae003e8f64b04c00cec13bc/streamvln/dataset/vln_action_dataset.py) | special-token、legacy 判断与 Qwen 预处理分派的匹配/修改片段 | StreamVLN 作者；该版本仓库声明 CC BY-NC-SA 4.0 |

训练文件头的版权与来源摘要如下：

```text
Adopted from https://github.com/lm-sys/FastChat.
Adopted from tatsu-lab@stanford_alpaca.
Copyright 2023 Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann Dubois, Xuechen Li
Licensed under the Apache License, Version 2.0.
```

本项目的兼容修改包括：选择 slow tokenizer、按 token 字符串获取 special-token ID、兼容缺失的 `legacy` 属性、添加 Qwen 分派，以及将词表大小与 `lm_head.out_features` 对齐。它们由本项目维护者添加，不应归因于上游原作者；其中对受 CC BY-NC-SA 4.0 保护内容的改编贡献，同样按 CC BY-NC-SA 4.0 提供。这里没有将上游 Apache 部分改授 CC，也没有把 CC 部分改授 MIT。

随仓库保留 [Apache-2.0 全文](LICENSES/Apache-2.0.txt) 和 [CC-BY-NC-SA-4.0 全文](LICENSES/CC-BY-NC-SA-4.0.txt)。对应标准文本来源为 [SPDX License List](https://github.com/spdx/license-list-data/tree/main/text)；权利义务以适用的许可原文为准。

### Transformers 5 限定兼容补丁

新增的 [`adapter/compat_assets/streamvln-v5.patch`](aima-open-session-experiment/adapter/compat_assets/streamvln-v5.patch) 包含固定 StreamVLN revision 的上下文和改编内容，不按本项目 MIT 统一授权。涉及的文件、前后 SHA-256 与补丁哈希列于同目录 [manifest.json](aima-open-session-experiment/adapter/compat_assets/manifest.json)。原创应用/校验包装 `adapter/streamvln_compat.py` 仍适用 MIT；生成的上游文件继续保留原有版权、归属和适用条款。

补丁涉及 `llava/__init__.py`、`llava/model/__init__.py`、`llava/model/language_model/llava_qwen.py`、视觉塔/重采样器 builder、`siglip_encoder.py`、`llava/train/llava_trainer.py`，以及 StreamVLN 的训练、数据预处理、`stream_video_vln.py`。来源均为上表固定 StreamVLN 版本；其中 Qwen 文件的 Hao Zhang / Apache-2.0 头、训练入口的 FastChat / Stanford Alpaca / Apache-2.0 头及仓库 CC BY-NC-SA 4.0 声明分别保留，不互相替换。

本轮改编包含：隔离未使用的模型和 DPO 分支、按顶层 Qwen 字段规范化旧配置、迁移 SigLIP 配置读取、恢复基座嵌入的视觉参数、显式 chat-template 输出、修复 generation cache 准备与状态独立性、将单设备监督训练连接到维护版 Trainer、支持 loss 归一化及 safetensors 保存。受 CC BY-NC-SA 4.0 保护部分的改编贡献同样按该许可提供。调用 Transformers/PEFT 的公共 API 不意味着模型权重或其他资产获得这些库的代码许可。

## 外部运行依赖与模型

这些组件需要单独获取。本项目的许可证不替代其源码、权重、数据、平台使用条款或文件级许可。

| 组件 | 实验记录的 revision | 已核验的声明与边界 |
| --- | --- | --- |
| StreamVLN 源码 | `e48f6ff7e9201d93aae003e8f64b04c00cec13bc` | [该版本 README](https://github.com/InternRobotics/StreamVLN/blob/e48f6ff7e9201d93aae003e8f64b04c00cec13bc/README.md#-license) 明确声明 CC BY-NC-SA 4.0，文件内已有的第三方许可仍需保留。非商业条款意味着不能把完整 StreamVLN 组件称为不受用途限制的开源软件。 |
| GenieSim | `a04fe4f7fda0ec6e01ab652fa19094008312bf97` | [该版本 LICENSE](https://github.com/AgibotTech/genie_sim/blob/a04fe4f7fda0ec6e01ab652fa19094008312bf97/LICENSE) 声明 `source/geniesim` 和 `source/data_collection` 为 MPL-2.0，`source/scene_reconstruction` 包含多种许可；不能据此推断所有外部资产均同许可。 |
| StreamVLN real-world checkpoint | `7b0269ad28e7039a32627b950766c09b5a646f8e` | [固定版本元数据](https://huggingface.co/api/models/mengwei0427/StreamVLN_Video_qwen_1_5_r2r_rxr_envdrop_scalevln_real_world/revision/7b0269ad28e7039a32627b950766c09b5a646f8e) 未给出独立许可；本次检查的 README 为空、文件树没有 LICENSE。**未确认权重授权，不将代码许可自动套用到权重。** |
| SigLIP `google/siglip-so400m-patch14-384` | `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | [固定版本模型卡元数据](https://huggingface.co/api/models/google/siglip-so400m-patch14-384/revision/9fdffc58afc957d1a03a25b10dba0329ab15c2a3) 标注 Apache-2.0；模型不随本项目 MIT 重新授权。 |
| Isaac Sim、PyTorch、Transformers、PEFT、其他运行依赖 | 取决于实际安装 | 按各自发行版与组件条款使用；本仓库未提供这些组件的统一许可或完整软件物料清单。 |

**历史说明更正：** 部分旧实验文档称“StreamVLN 仓库未明确声明许可”，这一判断不准确：上述实际使用的源码版本已经声明 CC BY-NC-SA 4.0。源码与 checkpoint 是不同的授权对象；checkpoint 的独立授权仍未确认。原始日志与 run-manifest 保留不改，避免改写实验历史。

## 不在 MIT 授权范围内的内容

- `aima-open-session-experiment/assets/**`：截图、录屏、配音、AI 图像、封面、音乐与合成媒体。具体来源、第三方权利、生成服务条款和单独授权记录应分别检查；没有统一再分发授权。
- `aima-open-session-experiment/artifacts/equivalent-scene/**`：PLY、USD/USDA/USDZ 及场景代理。由仿真观测或第三方场景生成，不意味着上游资产权利消失。
- 外部模型检查点、LoRA 权重、第三方数据集、第三方源码 checkout，以及任何商标、标识、肖像或声音权利。
- 文档中嵌入的第三方媒体、引用与源码片段；原创文字的 MIT 许可不覆盖这些被引用的对象。
- Release `local-workspace-backup-2026-10-23` 的完整历史工作区备份。它是归档，不是统一 MIT 发行包；新许可证不追溯地为其中所有文件增加授权。

这些排除说明只用于避免错误重新授权，**不等于为已经公开的第三方素材补齐了分发许可**。需要商业使用、重新发布完整媒体/数据/权重或发布集成产品时，应先向相关权利人核实并取得所需授权。

## 归属与问题反馈

感谢 AgibotTech / GenieSim、InternRobotics / StreamVLN、FastChat、Stanford Alpaca、Google / SigLIP 及相关上游贡献者。本项目与上述项目或机构没有隶属或背书关系。

若发现许可遗漏或归属问题，请通过 [GitHub Issues](https://github.com/eust-w/zhiyuan/issues) 提供文件路径、版本与来源；不要在公开 Issue 中提交凭据、私有数据或未获授权的材料。
