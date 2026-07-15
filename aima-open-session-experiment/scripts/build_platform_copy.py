"""Build platform-native draft copy from one factual content inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sanitize(text: str) -> str:
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b", "本机回环端口", text)
    text = re.sub(r"/root/[^\s`，。；：]+", "持久盘实验目录", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "已脱敏邮箱", text)
    return text


def read_text(root: Path, relative: str) -> str:
    return sanitize((root / relative).read_text(encoding="utf-8"))


def coherent_excerpt(text: str, limit: int) -> str:
    """Return complete Markdown paragraphs without carrying local media links."""

    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    selected: list[str] = []
    length = 0
    for paragraph in paragraphs:
        added = len(paragraph) + (2 if selected else 0)
        if selected and length + added > limit:
            break
        if not selected and added > limit:
            selected.append(paragraph[:limit].rsplit("。", 1)[0] + "。")
            break
        selected.append(paragraph)
        length += added
    return "\n\n".join(selected)


def facts_line(facts: dict[str, object]) -> str:
    return (
        f"唯一指标源为 `eval_result.json`；主指标 success@0.5m：base {facts['base_success_0_5']}，"
        f"LoRA {facts['lora_success_0_5']}。3m 只作辅助：base {facts['base_success_3']}，LoRA {facts['lora_success_3']}；"
        f"平均最终距离分别为 {facts['base_final_distance_m']}m 与 {facts['lora_final_distance_m']}m，"
        f"碰撞尝试分别为 {facts['base_collisions']} 与 {facts['lora_collisions']}。"
    )


def faq(stage: str) -> str:
    common = [
        ("这是不是课程官方方案？", "不是。流程参考 AIMA 指南，使用公开组件和自采等价兼容资产；课程私有包和课程原始资产没有被冒充。"),
        ("为什么不把一条成功轨迹当成绩？", "因为主指标是同一批十条 held-out episode 的总体统计，单条轨迹不能代表泛化。"),
        ("为什么要标注 AI 示意图？", "流程图和解释动画只帮助理解，不作为实验指标；指标只来自日志、截图和唯一 JSON 指标源。"),
        ("能否直接复现实验？", "可以按仓库文档复核公开接口和证据，但私有权重、课程私有包和外部服务不随仓库传播。"),
        ("下一步是什么？", "补齐课程等价 USD mesh、复核深度安全门和相机域，再在同一评测协议下重跑。"),
    ]
    if stage == "stage0":
        common[1] = ("blocked 后为什么要看 pose？", "只看 blocked 字段不够，拒绝前后 pose 必须一致，才能证明安全门没有偷偷改变状态。")
    elif stage == "stage1":
        common[1] = ("为什么 annotations 和 sidecar 要分开？", "公开动作数组保持 StreamVLN 约定，完整 STOP、depth、轨迹和目标信息放旁路记录，避免格式互相污染。")
    elif stage == "stage2":
        common[1] = ("loss 下降是不是成功？", "不是。loss 只说明优化发生过，adapter 重载和导航闭环必须单独验收。")
    elif stage == "stage3":
        common[1] = ("0/10 是不是说明闭环没跑？", "不是。模型→适配器→仿真→下一帧的真实闭环已经跑通，但到达零点五米的主成功率仍为 0/10。")
    return "\n".join(f"**问：{q}**\n\n答：{a}" for q, a in common)


def build_zhihu(root: Path, item: dict[str, object], facts: dict[str, object]) -> str:
    stage = str(item["episode"])
    source = read_text(root, str(item["source_doc"]))
    narration = read_text(root, str(item["narration"]))
    # Keep each platform draft within the requested 3000–5000 Chinese
    # character range while linking the full local evidence documents.
    source_excerpt = coherent_excerpt(source, 1180) + "\n\n（完整阶段文档见仓库链接，发布时可继续展开命令与截图说明。）"
    narration_excerpt = coherent_excerpt(narration, 900) + "\n\n（完整旁白脚本保留在 series/narration/，用于视频合成。）"
    evidence = "\n\n".join(
        f"![{stage} 证据图 {index}](../../{path})\n\n图 {index}：`{path}`（按画面角标区分真实录屏、真实结果图与 AI 示意图）"
        for index, path in enumerate(item["evidence_images"], 1)
    )
    sections = [
        f"# {item['title']}｜知乎教程草稿",
        "\n> 发布前状态：草稿。统一署名“智元布道师”，统一声明为非官方等价适配。素材中的真实录屏、真实结果图和 AI 示意图会在成片与图片上分别标注。",
        f"\n## 开场：{item['hook']}",
        f"\n本篇不是成功案例包装，而是一份可审计的实验教程。{facts_line(facts)} 本篇只讨论 {stage} 的方法和边界，3m 不替代 0.5m 主指标。",
        "\n## 实验背景与边界",
        "\n" + source_excerpt,
        "\n## 按画面顺序讲解",
        "\n" + narration_excerpt,
        "\n## 读者可以照着做的验收表",
        "\n| 门槛 | 通过条件 | 失败时怎么处理 |\n|---|---|---|\n"
        "| 环境/资产 | 场景、相机与等价资产可打开 | 先记录阻塞，不把预览当课程原件 |\n"
        "| 数据/观测 | 数量、schema、RGB-D、pose 和路径检查通过 | 删除坏 episode，不能静默跳过 |\n"
        "| 模型/闭环 | 日志无 NaN，动作与下一帧可追溯 | 回到对应 stage 修复，不能改指标 |\n"
        "| 媒体/公开稿 | 分辨率、字幕、敏感信息扫描通过 | 标记草稿，用户确认后再投稿 |",
        "\n## 证据索引（10–14 张）",
        "\n" + evidence,
        "\n## 失败边界与复盘",
        "\n本系列把“做到了什么”和“没有做到什么”放在同一篇文章里。控制器验证只能证明动作和距离计算可工作；LoRA 的低 loss 只能证明训练信号发生；模型的真实闭环只能证明接口连通。任何一项都不能替代同批 held-out 的总体 success。课程私有适配包、原始课程 USD、私有 checkpoint 和 adapter 不随公开稿传播。",
        "\n## 常见问题",
        "\n" + faq(stage),
        "\n## 结尾互动",
        "\n欢迎在评论区指出：如果你要复核这一阶段，最先会检查动作映射、数据 schema、训练重载，还是 held-out 指标？请优先讨论可复核证据，不要把示意图当原始实验画面。",
    ]
    return "\n".join(sections) + "\n"


def build_bilibili(root: Path, item: dict[str, object], facts: dict[str, object]) -> str:
    stage = str(item["episode"])
    chapters = {
        "stage0": ["00:00 本集问题与边界", "01:00 场景和头部相机", "03:00 四动作映射", "05:00 两帧等待与主线程", "07:30 blocked 与 pose 对照", "10:00 验收结论"],
        "stage1": ["00:00 为什么先做冒烟", "01:30 固定种子和拆分", "04:00 RGB-D-Pose 同步", "06:30 annotations 与 sidecar", "09:00 五厘米栅格探针", "12:00 批量验收与抽查"],
        "stage2": ["00:00 loss 的误读", "01:30 环境隔离", "04:00 LoRA 参数", "06:00 四道验证门", "09:00 59 步和显存", "12:00 adapter 重载边界"],
        "stage3": ["00:00 为什么公开失败", "01:30 同批 held-out 设计", "04:00 base/LoRA 动作闭环", "07:00 0.5m 与 3m 指标", "10:00 距离、碰撞、动作统计", "13:00 域差异与下一轮"],
    }[stage]
    tags = ["具身智能", "机器人", "视觉语言导航", "GenieSim", "StreamVLN", "LoRA", "仿真", "实验复盘"]
    desc = (
        f"本期主题：{item['title']}。这是参考 AIMA 流程的非官方等价适配教程，使用公开组件与自采等价兼容资产，不声称复制课程私有资产，也不是课程官方方案。"
        "整期按照‘问题钩子—真实录屏—命令与原理—验收证据—失败边界—复盘’展开，适合边看边对照仓库中的日志、截图、动图和 JSON。"
        f"本期只展示可复核的控制、数据、训练或闭环证据。{facts_line(facts)}"
        "0.5m 是唯一主成功半径，3m 只作辅助观察；控制器通过不等于模型导航成功，单条漂亮轨迹也不能替代同批十条 held-out 的总体统计。"
        "如果画面是现场采集，左上角会标‘真实录屏’；来自日志或评测 JSON 的图会标‘真实结果图’，流程关系图会标‘AI 示意图’，三者不互相冒充。"
        "视频不会展示账号、邮箱、实例编号、IP、SSH、私有权重或 adapter；课程私有适配包和原始课程资产也不会被包装成已经获得。"
        "观看时建议先暂停章节时间轴，复核动作映射、两帧等待、RGB-D 与 pose 同步、公开 annotations 与 sidecar 的边界，再看 Stage 3 的 base/LoRA 配对指标。"
        "本期结论只对当前公开组件、等价兼容 USD/PLY 资产和记录的运行配置负责；如果你的环境、相机域或 mesh 不同，应重新跑验收而不是直接引用结果。"
        "发布前还会跑一遍字幕行长、分辨率、帧率、音频、黑帧和敏感信息检查；这些检查未通过时，视频只保留在草稿目录，不会因为画面更好看就跳过证据门。"
        "想跟做的读者可以先从本期对应的 Stage 文档开始，再用同一套命令替换自己的公开资产；遇到失败请保留原始日志，先说明失败发生在哪一道门。"
    )
    return "\n".join([
        f"# {stage.upper()}｜B 站投稿包",
        "\n## 三个标题候选",
        "\n" + "\n".join(f"{i}. {title}" for i, title in enumerate(item["bilibili_titles"], 1)),
        "\n## 章节时间轴（粗剪计划，正片完成后以 SRT 和成片复核为准）",
        "\n" + "\n".join(f"- {chapter}" for chapter in chapters),
        "\n## 投稿简介",
        "\n" + desc,
        "\n## 标签",
        "\n" + " ".join(f"#{tag}" for tag in tags),
        "\n## 置顶评论",
        f"\n这一期最想让大家复核的是：{item['hook']}。你可以从证据索引对应的日志、截图和 `eval_result.json` 开始，不要把 AI 示意图当作原始仿真画面。需要补充哪一个验收命令，欢迎留言。",
        "\n## 五组常见问答",
        "\n" + faq(stage),
        "\n## 动态预告",
        f"\n下一期会继续讲：{item['title']} 的前置证据如何进入下一阶段。主指标、失败边界和素材标签都会保留。",
        "\n## 投稿状态",
        "\n素材完成 → 用户登录 → 草稿预览 → 用户确认最终提交 → 审核中。验证码、扫码、封面终审和最终发布由用户完成。",
        "",
    ])


def build_xhs(root: Path, item: dict[str, object], facts: dict[str, object]) -> str:
    stage = str(item["episode"])
    card_lines = "\n\n".join(
        f"{i}. {card}\n\n![{stage} 步骤卡 {i}](../../assets/series/xiaohongshu/{stage}/card-{i:02}.png)"
        for i, card in enumerate(item["cards"], 1)
    )
    body = (
        f"今天把 {item['title']} 拆成一组步骤卡。开头先回答一个问题：{item['hook']} "
        "我没有把一张漂亮的截图当成成功证据，而是把现场录屏、结果图、日志和示意图分开标注。"
        "先看第 1 张钩子图，再按动作、观测、文件、指标和复盘的顺序往下滑，每一张卡都对应一个可检查的证据点。"
        f"\n\n{facts_line(facts)}"
        "\n\n动作层要先锁定 STOP=0、前进=1、左转=2、右转=3，并确认移动后等待两个渲染帧；数据层要同时留下 RGB、depth、pose、距离和 blocked，不能只保存一张截图。"
        "公开 annotations 只保留 StreamVLN 约定的动作数组，完整 STOP、深度、轨迹和目标信息放到 sidecar；这样既能复核，也不会污染公开格式。"
        "训练层要把 dataset-only、单批前后向、完整更新和新进程重载拆开验收；loss 下降只是训练信号，不是导航成绩。"
        "评测层固定同一批十条 held-out，success@0.5m 是主指标，3m 只做辅助；最终距离、路径、碰撞和动作数一起看，不能挑一条成功轨迹代替总体结果。"
        "\n\n避坑清单：不要混用动作 ID；不要在动作后立刻抓图；不要把最终 STOP 塞进公开 annotations；不要用 loss 下降替代 held-out；不要把 3m 辅助结果写成 0.5m 主结果；不要把 AI 示意图当真实仿真画面。"
        "\n\n这是非官方等价适配，不声称复制课程私有资产，也不传播私有权重。评论区想看哪一步的命令和验收截图？如果你正在复现，欢迎按‘动作安全门 / 数据 sidecar / LoRA 重载 / 配对指标’留言，我会优先补对应证据。"
    )
    return "\n".join([
        f"# {stage.upper()}｜小红书步骤卡发布包",
        "\n## 首图钩子",
        f"\n{item['title']}\n\n{item['hook']}",
        "\n## 8–10 张卡片顺序",
        "\n" + card_lines,
        "\n## 正文（建议 800–1000 字，发布前按最终图片微调）",
        "\n" + body,
        "\n## 避坑清单",
        "\n- 真实录屏、真实结果图、AI 示意图必须分标签。\n- 主成功半径固定为 0.5m。\n- 不写账号、邮箱、IP、实例 ID、SSH 或私有权重。\n- 统一使用“非官方等价适配”，不宣称课程官方方案或排行成绩。",
        "\n## 评论互动",
        "\n你更想先看动作安全门、数据 sidecar、LoRA 重载，还是 base/LoRA 配对指标？留言后按证据文件继续补图。",
        "",
    ])


def build_douyin(root: Path, item: dict[str, object], facts: dict[str, object]) -> str:
    stage = str(item["episode"])
    script = (
        f"开头 0–6 秒：{item['title']}。\n"
        f"6–18 秒：{item['hook']}\n"
        "18–36 秒：展示一段真实录屏，叠加动作 ID、目标距离或 blocked 状态；画面角标写“真实录屏”。\n"
        f"36–50 秒：{facts_line(facts)}\n"
        "50–65 秒：展示真实结果图和一张 AI 示意图，明确区分标签。\n"
        "65–75 秒：结尾写“非官方等价适配，失败也公开；完整教程见 B 站与知乎”。"
    )
    return "\n".join([
        f"# {stage.upper()}｜抖音 60–75 秒竖屏预告",
        "\n## 三个标题候选",
        "\n" + "\n".join(f"{i}. {title}" for i, title in enumerate(item["douyin_titles"], 1)),
        "\n## 旁白与画面脚本",
        "\n" + script,
        "\n## 视频简介",
        f"\n{item['title']}。这是参考 AIMA 流程的非官方等价适配，真实录屏、真实结果图和 AI 示意图分开标注。{facts_line(facts)}不提交榜单，不宣称排行成绩，不传播私有权重。",
        "\n## 置顶评论",
        f"\n你觉得这一期最该先修哪一层？{item['hook']} 欢迎按证据讨论。",
        "\n## 标签",
        "\n#具身智能 #机器人 #视觉语言导航 #GenieSim #StreamVLN #真实实验 #失败复盘",
        "\n## 发布状态",
        "\n先保存草稿，用户完成登录、验证码/扫码、封面终审和最终发布。",
        "",
    ])


def build_package(root: Path, inventory: Path, output: Path) -> list[Path]:
    data = json.loads(inventory.read_text(encoding="utf-8"))
    facts = data["shared_facts"]
    output.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    readme = [
        "# 四期教程平台原生发布包",
        "",
        f"状态：{data['status']}。{data['disclaimer']}",
        "",
        f"指标源：`{data['metric_source']}`；主指标：`{data['primary_metric']}`。",
        "",
        "本目录按 B 站、知乎、小红书、抖音分别编排，不把横屏成片直接裁切成竖屏稿。所有平台先保存草稿，用户完成最终发布。",
        "",
    ]
    for item in data["episodes"]:
        stage = str(item["episode"])
        outputs = {
            f"bilibili-{stage}.md": build_bilibili(root, item, facts),
            f"zhihu-{stage}.md": build_zhihu(root, item, facts),
            f"xiaohongshu-{stage}.md": build_xhs(root, item, facts),
            f"douyin-{stage}.md": build_douyin(root, item, facts),
        }
        for name, content in outputs.items():
            path = output / name
            path.write_text(content, encoding="utf-8")
            generated.append(path)
            readme.append(f"- [{name}]({name})")
        readme.append(f"- [小红书 Stage {stage[-1]} 卡片目录](../../assets/series/xiaohongshu/{stage}/)")
    readme.extend([
        "",
        "## B 站封面草稿",
        "",
        *[f"- [Stage {index} 封面](../../assets/series/covers/stage{index}-cover.png)" for index in range(4)],
        "",
        "## 四期长片粗剪（明确不是最终发布）",
        "",
        "以下视频已达到约 10–12 分钟，用于校对沉稳男声、章节节奏、字幕容器和音频混音；画面会循环 60 秒样片，并烧录“粗剪草稿｜旧素材片段复用｜未满足最终比例”标识。GPUFree 新补录和真实录屏比例未通过前，不得发布。",
        "",
        *[
            f"- [Stage {index} 粗剪](../../assets/series/long-drafts/stage{index}/stage{index}-rough-cut-draft.mp4) · "
            f"[SRT](../../assets/series/long-drafts/stage{index}/stage{index}-rough-cut-draft.srt) · "
            f"[清单](../../assets/series/long-drafts/stage{index}/stage{index}-rough-cut-manifest.json)"
            for index in range(4)
        ],
    ])
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    generated.append(output / "README.md")
    return generated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=ROOT / "content/series/platform-content.json")
    parser.add_argument("--output", type=Path, default=ROOT / "article/series")
    args = parser.parse_args()
    generated = build_package(ROOT, args.inventory.resolve(), args.output.resolve())
    print(json.dumps({"generated": [str(path) for path in generated]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
