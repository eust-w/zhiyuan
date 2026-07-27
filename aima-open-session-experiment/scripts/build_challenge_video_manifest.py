"""Build the evidence-first 11-minute navigation challenge storyboard."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.challenge_video_contract import (
        APPROVED_CERTIFICATE_COPY,
        evidence_snapshot,
        public_repo_path,
        scan_public_bundle,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` invocation.
    from challenge_video_contract import (
        APPROVED_CERTIFICATE_COPY,
        evidence_snapshot,
        public_repo_path,
        scan_public_bundle,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "geniesim-streamvln-challenge-video/v1"
CHAPTER_TARGETS: dict[str, float] = {
    "hook": 65,
    "baseline": 70,
    "operation": 95,
    "data": 95,
    "training": 95,
    "paired_eval": 115,
    "innovation": 95,
    "closing": 60,
}
CHAPTER_IDS = list(CHAPTER_TARGETS)
REQUIRED_SEGMENT_FIELDS = {
    "segment_id",
    "chapter_id",
    "source",
    "source_type",
    "evidence_ref",
    "duration_s",
    "source_in_s",
    "source_out_s",
    "narration_section",
    "subtitle",
    "overlay",
    "public_label",
}

REAL_OPERATION = [
    "assets/series/recapture/raw/stage0-rgb-replay.mp4",
    "assets/series/recapture/raw/stage0-blocked-replay.mp4",
]
REAL_DATA = ["assets/series/recapture/raw/stage1-train1001-replay.mp4"]
REAL_TRAINING = [
    "assets/series/recapture/raw/stage2-single-batch-replay.mp4",
    "assets/series/recapture/raw/stage2-adapter-reload-replay.mp4",
]
REAL_HOOK = [
    "assets/series/recapture/raw/stage23-evidence/base-one-annotated.mp4",
    "assets/series/recapture/raw/stage23-evidence/lora-one-annotated.mp4",
]
PAIRED = [
    f"assets/series/recapture/canonical/{variant}-eval-{seed}-annotated.mp4"
    for seed in range(2001, 2011)
    for variant in ("base", "lora")
]
PAIR_DURATIONS: dict[int, tuple[float, float]] = {
    2001: (6, 5),
    2002: (5, 4),
    2003: (4, 5),
    2004: (6, 4),
    2005: (4, 4),
    2006: (5, 4),
    2007: (6, 4),
    2008: (5, 3),
    2009: (6, 4),
    2010: (8, 8),
}

EVAL_EVIDENCE = "experiments/exp02-equivalent-v3/eval_result.json"
STAGE0_EVIDENCE = "experiments/exp02-equivalent-v3/stage0-forward-check.json"
DATA_EVIDENCE = "experiments/exp02-equivalent-v3/dataset-validation.json"
TRAIN_EVIDENCE = "experiments/exp02-equivalent-v3/stage2_result_v2.json"


@lru_cache(maxsize=None)
def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def narration_character_count(sections: Iterable[dict[str, Any]]) -> int:
    text = "".join(str(section.get("text", "")) for section in sections)
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))


def narration_sections() -> list[dict[str, str]]:
    return [
        {
            "chapter_id": "hook",
            "title": "机器人动起来以后，挑战才真正开始",
            "text": (
                "画面里的机器人已经能在货架之间前进、转向，也能根据头部相机看到的画面输出下一步动作。"
                "但它会动，并不等于它会导航。真正要验证的是一条完整链路：语言指令进入模型，模型根据当前图像给出动作，"
                "动作驱动仿真，新的图像、深度、位姿和目标距离再回到下一轮推理，直到模型主动停止或达到步数上限。"
                "这次挑战不挑最好看的一条轨迹，而是保留同一批十条未知轨迹，把基础模型和微调模型放在完全相同的起点上比较。"
                "画面会同时展示成功、失败、绕行、过早停止和安全门拦截。重点不是把结果包装得漂亮，而是回答三个问题："
                "链路是否真的闭合，训练是否真的发生，模型是否真的更接近目标。"
            ),
        },
        {
            "chapter_id": "baseline",
            "title": "先定义一条可以复核的闭环",
            "text": (
                "实验场景是 market_00_g2，机器人使用 G2 Omnipicker 和头部前向相机，目标是一块醒目的红色标记。"
                "这里采用平面刚体导航，只验证视觉语言导航链路，不把画面中的平移描述成人形步态。"
                "动作空间固定为四个离散动作：零是停止，一是向前二十五厘米，二是左转十五度，三是右转十五度。"
                "每次动作完成后至少等待两个渲染帧，再同步保存彩色图、深度、四乘四位姿、目标距离以及是否被阻挡。"
                "模型请求和仿真执行由队列隔开，所有场景操作仍留在主线程，这样不会因为网络线程抢占而制造难以复现的状态。"
                "服务只监听本机回环地址；视频中不展示地址、连接信息或机器标识。接下来每一个数字和画面，都能回到对应的结果文件。"
            ),
        },
        {
            "chapter_id": "operation",
            "title": "真实操作：动作、观察与安全门",
            "text": (
                "先看最基础的动作验证。机器人执行前进后，平面位移应接近二十五厘米；执行左右转后，航向增量应接近十五度；"
                "停止动作不再改变位姿。键盘阶段还保留后退用于人工排查，但训练动作空间只有停止、前进、左转和右转。"
                "更重要的是障碍验证：当前方中心深度低于安全阈值时，前进请求会被拒绝，blocked 变为真，位姿矩阵保持不变。"
                "画面里的碰撞计数实际记录的是这种安全门拦截的前进尝试，不代表机器人已经穿进货架或发生实体撞击。"
                "每一步落盘后，接口返回 step_id、彩色图路径、深度路径、位姿、目标距离、阻挡状态以及终止状态。"
                "同一个 request_id 如果重发，只返回缓存结果，不重复移动。这样既能处理网络重试，也能保证动作统计不会被重复请求污染。"
                "这部分看似只是让机器人走几步，却决定了后面采集和评测是否可信：如果动作增量、帧同步或阻挡语义不稳定，"
                "再漂亮的训练曲线也无法说明模型学会了导航。"
            ),
        },
        {
            "chapter_id": "data",
            "title": "数据结构：五十条训练与十条未知轨迹",
            "text": (
                "数据采集先运行三条冒烟轨迹，用来检查目录、图像解码和动作长度；通过后再使用固定种子生成五十条训练轨迹，"
                "种子从一千零一到一千零五十。评测使用另一组十条固定种子，从两千零一到两千零一十，训练阶段看不到这些轨迹。"
                "起点和目标必须处在同一可达连通区，优先选择二到六米的距离，再由带二十四个朝向的平面搜索器生成参考路径。"
                "StreamVLN 使用的 annotations.json 保存图像序列、指令和动作标签，首动作是负一，图像数量与动作数组严格一致，"
                "末尾停止动作不写进这个训练标注。完整的停止、深度、位姿轨迹、目标位置、阻挡记录和终止原因，则写入独立 sidecar。"
                "把两者分开，是为了既满足训练读取格式，又不丢失复核闭环所需的仿真细节。"
                "每条轨迹还要通过帧数、动作数、相对路径、文件边界、图像可解码和碰撞字段检查。"
                "最终五十条训练和十条评测全部有效；视频展示的是其中一条真实采集轨迹与对应目录结构，不用示意数据冒充真实样本。"
            ),
        },
        {
            "chapter_id": "training",
            "title": "训练过程：损失下降只能证明训练跑通",
            "text": (
                "仿真和训练使用彼此隔离的 Python 环境。仿真继续使用 Isaac 自带环境，StreamVLN 则在独立的 Python 三点九环境中加载模型，"
                "避免为了训练升级依赖后破坏场景运行。LoRA 参数固定为秩八、缩放十六、丢弃率百分之五，训练一轮，批量为一，"
                "学习率二乘十的负五次方，使用 BF16 和梯度检查点，调节部分限定为多模态 LoRA 层。"
                "正式训练之前依次通过四道门：只读取数据集，执行单批前向和反向，完成全量训练，再在新进程中重新加载适配器。"
                "单批测试得到有限且非零的损失和梯度，说明标签没有全部被掩码。完整训练记录五十九个有效更新步，"
                "首步损失零点四一六七，末步零点零八二三，最大梯度范数保持有限，峰值显存约二十七点一九 GiB，"
                "没有出现显存溢出、非数或无穷值。新进程重载通过，说明保存的适配器可以再次装载。"
                "但是损失下降只说明模型拟合了这批监督数据，重载通过只说明文件结构可用；二者都不能替代闭环导航成功率。"
                "所以训练结束后必须回到相同未知轨迹，让模型自己产生动作。"
            ),
        },
        {
            "chapter_id": "paired_eval",
            "title": "配对评测：同一批十条轨迹逐条对照",
            "text": (
                "现在进入最关键的配对评测。基础模型和 LoRA 都使用 eval 二零零一到二零一零这十条轨迹，"
                "每一条都从相同起点和目标开始；每次重置缓存、历史记忆和动作队列，最多执行二百步，非法输出安全转换为停止。"
                "画面按照同一个编号先放基础模型，再放 LoRA，十组轨迹全部进入汇总，不用单条较好的表现代替总体结果。"
                "二零零一可以看到两个模型都没有进入半米成功圈；随后八组采用较快节奏展示转向、前进、停止和被安全门拦截的差异；"
                "二零零九的基础模型多次尝试前进并达到步数上限，是安全拦截较集中的失败案例；最后用二零一零收束整批对照。"
                "主指标半米成功率，基础模型是零比十，LoRA 也是零比十，因此两者的半米 SPL 都是零。"
                "三米只作为辅助观察，基础模型有两条进入三米范围，LoRA 有一条。基础模型平均最终距离约三点九九米，"
                "LoRA 约四点六九米。安全门拦截的前进尝试分别为一百三十二次和四十五次。"
                "这些结果说明闭环和配对评测真实运行了，但这次微调没有在半米目标上带来提升；"
                "LoRA 动作更少、拦截更少，也可能来自更早停止，而不是更好的导航。判断改进必须同时看成功、距离、路径、步数和动作分布。"
            ),
        },
        {
            "chapter_id": "innovation",
            "title": "创新挑战：从跑通 baseline 到真正改进",
            "text": (
                "零比十不是故事的终点，而是下一轮创新的起点。第一条方向是场景与目标多样性：增加不同货架布局、光照、遮挡和目标外观，"
                "检查模型是否只记住红色标记和固定通道。第二条方向是数据多样性：加入更长路径、转角、死路、难负样本和指令改写，"
                "同时保持训练与评测严格隔离。第三条方向是算法：比较更长视觉记忆、显式局部地图、分层规划、动作平滑以及安全门反馈进入模型后的效果，"
                "避免模型在障碍前反复请求同一动作。第四条方向是评测：为过早停止、原地旋转、走反方向、安全门震荡和超步数建立失败分类，"
                "固定随机种子和版本，让每次改动都能与同一基线配对比较。"
                f"{APPROVED_CERTIFICATE_COPY}"
                "真正有说服力的创新不是再剪一条看起来成功的视频，而是在更多未知场景上让半米成功率、SPL 和最终距离稳定改善，"
                "并且能说明改善来自哪一项设计。"
            ),
        },
        {
            "chapter_id": "closing",
            "title": "结论：把失败也变成可复用资产",
            "text": (
                "回看整条链路，机器人动作、观察同步、五十条训练数据、十条未知轨迹、LoRA 五十九步训练、适配器重载以及 Base 与 LoRA 配对闭环都留下了可检查证据。"
                "结果也同样明确：半米成功率都是零比十，当前微调没有提升主指标。"
                "这并不意味着前面的工作没有价值，它把问题从会不会运行推进到了为什么没有泛化，也给下一轮场景、数据、记忆和规划实验建立了稳定对照。"
                "当新的方法出现时，不需要重新发明评测口径，只要在同一批轨迹和同一套指标上重新运行，就能看到改动究竟解决了什么。"
                "真正的挑战，不是做出一段演示，而是让每一个结果都经得起复核。"
            ),
        },
    ]


def _segment(
    *,
    chapter_id: str,
    slug: str,
    source: str,
    source_type: str,
    evidence_ref: str,
    duration_s: float,
    source_in_s: float,
    source_out_s: float,
    subtitle: list[str],
    overlay: str,
    public_label: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "segment_id": f"{chapter_id}-{slug}",
        "chapter_id": chapter_id,
        "source": source,
        "source_type": source_type,
        "evidence_ref": evidence_ref,
        "duration_s": duration_s,
        "source_in_s": source_in_s,
        "source_out_s": source_out_s,
        "narration_section": chapter_id,
        "subtitle": subtitle,
        "overlay": overlay,
        "public_label": public_label,
        "layout": "landscape",
        **extra,
    }


class _CanonicalAllocator:
    def __init__(self, root: Path):
        self.root = root
        self.sources = PAIRED
        self.cursor: dict[str, float] = {}
        for source in self.sources:
            match = re.search(r"(base|lora)-eval-(\d+)-annotated", source)
            if match is None:
                raise ValueError(f"unexpected canonical source: {source}")
            variant, seed_text = match.groups()
            pair = PAIR_DURATIONS[int(seed_text)]
            self.cursor[source] = pair[0 if variant == "base" else 1]
        self.index = 0

    def allocate(
        self,
        chapter_id: str,
        duration: float,
        slug_prefix: str,
        subtitle: list[str],
        overlay: str,
        evidence_ref: str = EVAL_EVIDENCE,
    ) -> list[dict[str, Any]]:
        remaining = duration
        result: list[dict[str, Any]] = []
        attempts = 0
        while remaining > 0.001:
            if attempts > len(self.sources) * 3:
                raise ValueError(f"not enough canonical footage for {chapter_id}")
            source = self.sources[self.index % len(self.sources)]
            self.index += 1
            attempts += 1
            start = self.cursor[source]
            available = probe_duration(self.root / source) - start
            if available <= 0.02:
                continue
            take = min(remaining, available, 22.0)
            end = start + take
            self.cursor[source] = end
            result.append(
                _segment(
                    chapter_id=chapter_id,
                    slug=f"{slug_prefix}-{len(result) + 1:02d}",
                    source=source,
                    source_type="real_recording",
                    evidence_ref=evidence_ref,
                    duration_s=round(take, 3),
                    source_in_s=round(start, 3),
                    source_out_s=round(end, 3),
                    subtitle=subtitle,
                    overlay=overlay,
                    public_label="真实录屏",
                    allow_loop=False,
                )
            )
            remaining -= take
        return result


def _fixed_real(
    root: Path,
    chapter_id: str,
    source: str,
    evidence_ref: str,
    subtitle: list[str],
    overlay: str,
    *,
    duration: float | None = None,
    slug: str,
) -> dict[str, Any]:
    source_duration = probe_duration(root / source)
    take = source_duration if duration is None else duration
    if take > source_duration + 0.02:
        raise ValueError(f"source window exceeds {source}")
    return _segment(
        chapter_id=chapter_id,
        slug=slug,
        source=source,
        source_type="real_recording",
        evidence_ref=evidence_ref,
        duration_s=round(take, 3),
        source_in_s=0,
        source_out_s=round(take, 3),
        subtitle=subtitle,
        overlay=overlay,
        public_label="真实录屏",
        allow_loop=False,
    )


def _still(
    chapter_id: str,
    slug: str,
    source: str,
    evidence_ref: str,
    duration: float,
    subtitle: list[str],
    overlay: str,
    source_type: str = "real_evidence",
) -> dict[str, Any]:
    label = "流程示意" if source_type == "diagram" else "真实结果"
    return _segment(
        chapter_id=chapter_id,
        slug=slug,
        source=source,
        source_type=source_type,
        evidence_ref=evidence_ref,
        duration_s=duration,
        source_in_s=0,
        source_out_s=duration,
        subtitle=subtitle,
        overlay=overlay,
        public_label=label,
        allow_loop=False,
    )


def _interleave(
    real_segments: list[dict[str, Any]],
    still_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    real_index = 0
    still_index = 0
    while real_index < len(real_segments) or still_index < len(still_segments):
        if real_index < len(real_segments):
            result.append(real_segments[real_index])
            real_index += 1
        if still_index < len(still_segments):
            result.append(still_segments[still_index])
            still_index += 1
    return result


def _static_segments(chapter_id: str) -> list[dict[str, Any]]:
    specs: dict[str, list[tuple[str, str, float, str, list[str], str]]] = {
        "hook": [
            ("assets/screenshots/v3/stage3-paired-metrics.png", EVAL_EVIDENCE, 3, "半米成功率：0/10 对 0/10", ["先看真实结果"], "real_evidence"),
            ("assets/screenshots/v3/stage3-episode-distances.png", EVAL_EVIDENCE, 3, "十条未知轨迹全部进入汇总", ["不挑最好的一条"], "real_evidence"),
        ],
        "baseline": [
            ("assets/screenshots/v3/stage0-validation.png", STAGE0_EVIDENCE, 3, "场景、机器人、相机均已验证", ["先定义闭环"], "real_evidence"),
            ("assets/plots/evidence-chain.png", EVAL_EVIDENCE, 3, "指令 → 动作 → 仿真 → 新观察", ["每一步都能回查"], "diagram"),
            ("assets/plots/action-counts.png", EVAL_EVIDENCE, 3, "动作空间：停止、前进、左转、右转", ["四个离散动作"], "diagram"),
        ],
        "operation": [
            ("assets/screenshots/v3/stage0-forward-before.jpg", STAGE0_EVIDENCE, 3, "前进前位姿", ["记录动作前状态"], "real_evidence"),
            ("assets/screenshots/v3/stage0-forward-after.jpg", STAGE0_EVIDENCE, 3, "前进约 0.25 米", ["核对位移增量"], "real_evidence"),
            ("assets/screenshots/v3/stage0-before-block.jpg", STAGE0_EVIDENCE, 3, "障碍前请求前进", ["安全门检查深度"], "real_evidence"),
            ("assets/screenshots/v3/stage0-after-block.jpg", STAGE0_EVIDENCE, 3, "blocked=true，位姿不变", ["拒绝危险前进"], "real_evidence"),
            ("assets/plots/action-counts.png", EVAL_EVIDENCE, 3, "动作计数来自实际闭环", ["重复请求不重复移动"], "real_evidence"),
            ("assets/screenshots/v3/stage0-validation.png", STAGE0_EVIDENCE, 3, "RGB、depth、pose 同步", ["动作后等待两帧"], "real_evidence"),
        ],
        "data": [
            ("assets/screenshots/v3/stage1-validation.png", DATA_EVIDENCE, 3, "50 条训练 + 10 条评测", ["固定种子拆分"], "real_evidence"),
            ("assets/plots/schema-sidecar.png", DATA_EVIDENCE, 3, "训练标注与完整 sidecar 分离", ["两种结构各司其职"], "diagram"),
            ("assets/screenshots/v3/train-1001-start.jpg", DATA_EVIDENCE, 3, "训练轨迹起点", ["真实采集帧"], "real_evidence"),
            ("assets/screenshots/v3/train-1001-goal.jpg", DATA_EVIDENCE, 3, "红色目标标记", ["目标可见且可达"], "real_evidence"),
            ("assets/screenshots/v3/train-1025-mid.jpg", DATA_EVIDENCE, 3, "中段轨迹抽查", ["检查图像与动作"], "real_evidence"),
            ("assets/screenshots/v3/train-1050-mid.jpg", DATA_EVIDENCE, 3, "第 50 条训练轨迹抽查", ["全部样本通过检查"], "real_evidence"),
        ],
        "training": [
            ("assets/screenshots/v3/stage2-gates.png", TRAIN_EVIDENCE, 3, "四道训练验证门", ["数据、前后向、训练、重载"], "real_evidence"),
            ("assets/plots/lora-config.png", TRAIN_EVIDENCE, 3, "LoRA：r=8，alpha=16", ["参数固定可复核"], "diagram"),
            ("assets/plots/validation-gates.png", TRAIN_EVIDENCE, 3, "单批损失与梯度均非零", ["先证明标签有效"], "real_evidence"),
            ("assets/screenshots/v3/stage2-loss-curve.png", TRAIN_EVIDENCE, 3, "59 步：0.4167 → 0.0823", ["训练确实发生"], "real_evidence"),
            ("assets/plots/lora-config.png", TRAIN_EVIDENCE, 3, "峰值显存约 27.19 GiB", ["没有非数或无穷"], "real_evidence"),
            ("assets/screenshots/v3/stage2-gates.png", TRAIN_EVIDENCE, 3, "新进程适配器重载通过", ["文件可以再次装载"], "real_evidence"),
            ("assets/screenshots/v3/stage2-loss-curve.png", TRAIN_EVIDENCE, 3, "损失下降不等于导航成功", ["必须回到闭环评测"], "real_evidence"),
        ],
        "paired_eval": [
            ("assets/screenshots/v3/stage3-paired-metrics.png", EVAL_EVIDENCE, 3, "Base 与 LoRA 使用同一批十条", ["配对而不是挑样本"], "real_evidence"),
            ("assets/plots/metrics-base-lora.png", EVAL_EVIDENCE, 3, "半米成功率均为 0/10", ["主指标没有提升"], "real_evidence"),
            ("assets/screenshots/v3/stage3-episode-distances.png", EVAL_EVIDENCE, 3, "逐条最终距离", ["失败也进入汇总"], "real_evidence"),
            ("assets/plots/action-counts.png", EVAL_EVIDENCE, 3, "安全拦截：132 对 45", ["不是实体撞击"], "real_evidence"),
            ("assets/plots/episode-distance.png", EVAL_EVIDENCE, 3, "平均最终距离：3.99 米对 4.69 米", ["同时观察距离与动作"], "real_evidence"),
        ],
        "innovation": [
            ("assets/plots/next-roadmap.png", EVAL_EVIDENCE, 4, "方向一：场景与目标多样性", ["检验视觉泛化"], "diagram"),
            ("assets/plots/schema-sidecar.png", DATA_EVIDENCE, 4, "方向二：数据与难负样本", ["严格隔离训练评测"], "diagram"),
            ("assets/plots/evidence-chain.png", EVAL_EVIDENCE, 4, "方向三：记忆、规划与安全反馈", ["减少重复无效动作"], "diagram"),
            ("assets/plots/metrics-base-lora.png", EVAL_EVIDENCE, 4, "方向四：配对评测与失败分类", ["用指标证明改进"], "diagram"),
        ],
        "closing": [
            ("assets/screenshots/v3/stage3-paired-metrics.png", EVAL_EVIDENCE, 3, "闭环完成，主指标仍为 0/10", ["诚实记录当前结果"], "real_evidence"),
            ("assets/plots/next-roadmap.png", EVAL_EVIDENCE, 3, "下一轮从失败分类开始", ["建立稳定对照"], "diagram"),
            ("assets/plots/evidence-chain.png", EVAL_EVIDENCE, 3, "让每个结果经得起复核", ["证据链闭合"], "diagram"),
        ],
    }
    return [
        _still(
            chapter_id,
            f"evidence-{index:02d}",
            source,
            evidence_ref,
            duration,
            subtitle,
            overlay,
            source_type,
        )
        for index, (source, evidence_ref, duration, overlay, subtitle, source_type) in enumerate(
            specs[chapter_id],
            start=1,
        )
    ]


def _pair_segments(root: Path) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for seed in range(2001, 2011):
        for variant_index, variant in enumerate(("base", "lora")):
            duration = PAIR_DURATIONS[seed][variant_index]
            source = f"assets/series/recapture/canonical/{variant}-eval-{seed}-annotated.mp4"
            if duration > probe_duration(root / source) + 0.02:
                raise ValueError(f"paired replay is too short: {source}")
            public_variant = "Base" if variant == "base" else "LoRA"
            segments.append(
                _segment(
                    chapter_id="paired_eval",
                    slug=f"{seed}-{variant}",
                    source=source,
                    source_type="real_recording",
                    evidence_ref=EVAL_EVIDENCE,
                    duration_s=duration,
                    source_in_s=0,
                    source_out_s=duration,
                    subtitle=[f"eval-{seed} · {public_variant}", "模型自己产生动作"],
                    overlay=f"配对轨迹 {seed} · {public_variant}",
                    public_label="真实录屏",
                    allow_loop=False,
                    pair_episode_id=f"eval-{seed}",
                    pair_variant=variant,
                )
            )
    return segments


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    facts = evidence_snapshot(root)
    sections = narration_sections()
    allocator = _CanonicalAllocator(root)

    real_by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, source in enumerate(REAL_HOOK, start=1):
        real_by_chapter["hook"].append(
            _fixed_real(
                root,
                "hook",
                source,
                EVAL_EVIDENCE,
                ["真实 Base/LoRA 轨迹", "先看结果再拆流程"],
                "模型动作驱动仿真",
                slug=f"opening-{index:02d}",
            )
        )
    real_by_chapter["hook"].extend(
        allocator.allocate(
            "hook",
            38,
            "opening-context",
            ["不是剪一条成功轨迹", "十条全部进入汇总"],
            "同一批未知轨迹",
        )
    )

    real_by_chapter["baseline"] = [
        _fixed_real(
            root,
            "baseline",
            REAL_OPERATION[0],
            STAGE0_EVIDENCE,
            ["market_00_g2 场景", "G2 与头部相机"],
            "场景、机器人、相机",
            slug="scene-camera",
        ),
        _fixed_real(
            root,
            "baseline",
            REAL_OPERATION[1],
            STAGE0_EVIDENCE,
            ["四个离散动作", "动作后同步观察"],
            "STOP / 前进 / 左转 / 右转",
            slug="action-baseline",
        ),
    ]
    real_by_chapter["baseline"].extend(
        allocator.allocate(
            "baseline",
            33,
            "closed-loop",
            ["语言、图像、动作、仿真", "闭环持续更新"],
            "指令到新观察的闭环",
        )
    )

    real_by_chapter["operation"] = allocator.allocate(
        "operation",
        77,
        "operation",
        ["动作 ID、距离、blocked", "真实闭环持续运行"],
        "动作与安全门实时状态",
    )

    real_by_chapter["data"] = [
        _fixed_real(
            root,
            "data",
            REAL_DATA[0],
            DATA_EVIDENCE,
            ["单条真实数据采集", "RGB / depth / pose / action"],
            "train-1001 数据落盘",
            slug="train-1001",
        )
    ]
    real_by_chapter["data"].extend(
        allocator.allocate(
            "data",
            66.5,
            "dataset-context",
            ["固定种子生成轨迹", "训练与评测严格分开"],
            "五十条训练与十条未知轨迹",
        )
    )

    real_by_chapter["training"] = [
        _fixed_real(
            root,
            "training",
            REAL_TRAINING[0],
            TRAIN_EVIDENCE,
            ["单批前向与反向", "损失、梯度均有效"],
            "训练前单批验证",
            slug="single-batch",
        ),
        _fixed_real(
            root,
            "training",
            REAL_TRAINING[1],
            TRAIN_EVIDENCE,
            ["新进程重新加载", "适配器文件可用"],
            "LoRA adapter 重载",
            slug="adapter-reload",
        ),
    ]
    real_by_chapter["training"].extend(
        allocator.allocate(
            "training",
            50,
            "training-context",
            ["五十九个有效更新步", "损失下降不代表会导航"],
            "真实训练记录与闭环画面",
            TRAIN_EVIDENCE,
        )
    )

    real_by_chapter["paired_eval"] = _pair_segments(root)
    real_by_chapter["innovation"] = allocator.allocate(
        "innovation",
        79,
        "innovation-context",
        ["从失败轨迹寻找改进点", "场景、数据、算法、评测"],
        "创新挑战从可复核对照开始",
    )
    real_by_chapter["closing"] = allocator.allocate(
        "closing",
        51,
        "closing",
        ["保留成功也保留失败", "下一轮继续配对验证"],
        "把失败变成可复用资产",
    )

    segments: list[dict[str, Any]] = []
    for chapter_id in CHAPTER_IDS:
        segments.extend(_interleave(real_by_chapter[chapter_id], _static_segments(chapter_id)))
    for index, segment in enumerate(segments, start=1):
        segment["segment_id"] = f"{index:03d}-{segment['segment_id']}"

    total = sum(float(segment["duration_s"]) for segment in segments)
    real = sum(
        float(segment["duration_s"])
        for segment in segments
        if segment["source_type"] == "real_recording"
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "title": "GenieSim × StreamVLN 具身导航 baseline 与创新挑战",
        "public_framing": (
            "在 GenieSim 中搭建 StreamVLN 具身导航 baseline，完成数据采集、"
            "LoRA 训练和闭环评测，并探索进一步创新方向。"
        ),
        "chapter_ids": CHAPTER_IDS,
        "chapter_targets_s": CHAPTER_TARGETS,
        "duration_s": total,
        "real_recording_ratio": real / total,
        "metric_source": EVAL_EVIDENCE,
        "training_source": TRAIN_EVIDENCE,
        "paired_episode_ids": list(facts["heldout_episode_ids"]),
        "paired_replays": list(PAIRED),
        "facts": facts,
        "narration_sections": sections,
        "segments": segments,
    }
    public_hits = scan_public_bundle(manifest)
    if public_hits:
        raise ValueError("public challenge manifest is unsafe:\n" + "\n".join(public_hits))
    if not 2200 <= narration_character_count(sections) <= 2700:
        raise ValueError(
            f"narration must contain 2200-2700 Chinese characters; "
            f"got {narration_character_count(sections)}"
        )
    return manifest


def write_outputs(
    root: Path,
    manifest_path: Path,
    source_path: Path,
    narration_path: Path,
) -> dict[str, Any]:
    manifest = build_manifest(root)
    facts = manifest["facts"]
    narration = {
        "schema_version": "geniesim-streamvln-challenge-narration/v1",
        "character_count": narration_character_count(manifest["narration_sections"]),
        "sections": manifest["narration_sections"],
    }
    source = {
        "schema_version": "geniesim-streamvln-challenge-source/v1",
        "metric_source": manifest["metric_source"],
        "training_source": manifest["training_source"],
        "facts": facts,
        "sources": [
            {
                "source": segment["source"],
                "source_type": segment["source_type"],
                "evidence_ref": segment["evidence_ref"],
            }
            for segment in manifest["segments"]
        ],
    }
    for path, data in (
        (manifest_path, manifest),
        (source_path, source),
        (narration_path, narration),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {
        "manifest": public_repo_path(manifest_path, root),
        "source": public_repo_path(source_path, root),
        "narration": public_repo_path(narration_path, root),
        "duration_s": manifest["duration_s"],
        "real_recording_ratio": manifest["real_recording_ratio"],
        "narration_character_count": narration["character_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "content/challenge-video/challenge-manifest.json",
    )
    parser.add_argument(
        "--source-output",
        type=Path,
        default=ROOT / "content/challenge-video/challenge-source.json",
    )
    parser.add_argument(
        "--narration-output",
        type=Path,
        default=ROOT / "content/challenge-video/narration-sections.json",
    )
    args = parser.parse_args()
    result = write_outputs(
        ROOT,
        args.output.resolve(),
        args.source_output.resolve(),
        args.narration_output.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
