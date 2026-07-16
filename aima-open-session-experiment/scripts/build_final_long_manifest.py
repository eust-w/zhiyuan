"""Create the four-episode, evidence-driven final-long storyboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def canonical_sources(root: Path) -> list[str]:
    manifest_path = root / "assets/series/recapture/canonical/manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [item["output"] for item in data["media"]]


STATIC_SOURCES = {
    "stage0": [
        ("assets/carousel/carousel-01.jpg", "title_card", "article/series/bilibili-stage0.md"),
        ("assets/ai-diagrams/ai-01-perception-action.png", "ai_diagram", "docs/01-stage0-仿真环境验证.md"),
        ("assets/plots/evidence-chain.png", "metric_animation", "experiments/exp02-equivalent-v3/run-manifest.json"),
        ("assets/screenshots/v3/stage0-validation.png", "real_evidence", "docs/01-stage0-仿真环境验证.md"),
    ],
    "stage1": [
        ("assets/carousel/carousel-08.jpg", "title_card", "article/series/bilibili-stage1.md"),
        ("assets/plots/schema-sidecar.png", "metric_animation", "docs/02-stage1-数据采集.md"),
        ("assets/plots/validation-gates.png", "metric_animation", "docs/02-stage1-数据采集.md"),
        ("assets/ai-diagrams/ai-02-data-pipeline.png", "ai_diagram", "docs/02-stage1-数据采集.md"),
    ],
    "stage2": [
        ("assets/carousel/carousel-12.jpg", "title_card", "article/series/bilibili-stage2.md"),
        ("assets/screenshots/v3/stage2-loss-curve.png", "real_evidence", "runs/2026-07-13/stage2-training.stdout.log"),
        ("assets/plots/lora-config.png", "metric_animation", "experiments/exp02-equivalent-v3/stage2_result.json"),
        ("assets/ai-diagrams/ai-03-closed-loop.png", "ai_diagram", "docs/03-stage2-lora微调.md"),
    ],
    "stage3": [
        ("assets/carousel/carousel-20.jpg", "title_card", "article/series/bilibili-stage3.md"),
        ("assets/screenshots/v3/stage3-paired-metrics.png", "real_evidence", "experiments/exp02-equivalent-v3/eval_result.json"),
        ("assets/plots/metrics-base-lora.png", "metric_animation", "experiments/exp02-equivalent-v3/eval_result.json"),
        ("assets/ai-diagrams/ai-04-failure-roadmap.png", "ai_diagram", "docs/05-结果分析与排障.md"),
    ],
}


THEMES = {
    "stage0": {
        "title": "机器人会动，不等于导航闭环",
        "real": [
            "动作必须能复核，不能只看画面像是在移动。",
            "每次动作之后都等待两帧，再同步保存彩色图、深度和位姿。",
            "安全门返回受阻时，机器人位姿必须保持不变。",
            "停止、前进、左转和右转统一映射到公开动作编号。",
            "主线程执行仿真，服务线程只提交动作请求。",
        ],
        "static": [
            "这一页解释控制与观测之间的证据链。",
            "示意图只帮助理解，验收仍以真实日志和录屏为准。",
            "动作、距离、碰撞和位姿必须落在同一条记录里。",
            "阶段零通过，才有资格继续采集训练数据。",
        ],
        "overlay": "动作、观测、位姿与安全门必须同步",
    },
    "stage1": {
        "title": "五十条训练与十条评测如何采集",
        "real": [
            "固定种子让每条轨迹能够重复生成和逐项核验。",
            "公开标注保留训练所需字段，完整旁路记录保存停止、深度和碰撞。",
            "训练集与评测集从种子开始隔离，避免把评测样本混入训练。",
            "每条轨迹都检查帧数、动作数、路径和图像可解码性。",
            "留出轨迹不是漂亮样例，而是后续配对评测的统一输入。",
        ],
        "static": [
            "三条冒烟通过后，再进入五十条训练轨迹。",
            "公开标注与完整旁路记录承担不同职责。",
            "五厘米栅格和障碍膨胀用于规划与碰撞验收。",
            "失败轨迹也必须进入数据质量记录。",
        ],
        "overlay": "固定种子、数据隔离、双层标注与逐条验收",
    },
    "stage2": {
        "title": "损失下降为什么不代表会导航",
        "real": [
            "单批前后向先证明数据和梯度链路能够工作。",
            "五十九个有限更新步说明优化发生过，但不代表导航成功。",
            "适配器必须在新进程中重新加载，排除当前进程残留状态。",
            "训练日志、显存峰值和适配器哈希共同构成训练证据。",
            "真实闭环轨迹用来检验训练结果，而不是替训练曲线背书。",
        ],
        "static": [
            "损失从零点四一六七下降到零点零八二三。",
            "峰值显存约二十七点一九吉比字节。",
            "重载成功只能证明权重可用，不能证明机器人会到达目标。",
            "训练证据和导航证据必须分开报告。",
        ],
        "overlay": "数据检查、单批训练、完整训练、独立重载",
    },
    "stage3": {
        "title": "闭环真实，为什么半米成功仍为零比十",
        "real": [
            "模型读取头部相机并自己生成动作，控制器只负责安全执行。",
            "基础模型与低秩适配模型使用完全相同的十条留出轨迹。",
            "每帧叠加动作、距离、受阻、碰撞和实时轨迹。",
            "失败轨迹同样进入总体指标，不能只展示最好的一条。",
            "半米成功、路径效率、距离和碰撞都来自同一份评测结果。",
        ],
        "static": [
            "基础模型与低秩适配模型的半米成功均为零比十。",
            "路径效率为零并不否认闭环真实，只说明没有达到成功条件。",
            "域差异、深度安全门和场景几何共同影响最终结果。",
            "这一结果是非官方等价适配，不是官方榜单成绩。",
        ],
        "overlay": "同批十条留出轨迹，统一半米成功半径",
    },
}


def _real_sources(root: Path, stage: str) -> list[str]:
    canonical = canonical_sources(root)
    if stage == "stage3":
        return canonical
    if stage == "stage0":
        prefix = [
            "assets/series/recapture/raw/stage0-rgb-replay.mp4",
            "assets/series/recapture/raw/stage0-blocked-replay.mp4",
            "assets/series/recapture/raw/stage23-evidence/base-one-annotated.mp4",
            "assets/series/recapture/raw/stage23-evidence/lora-one-annotated.mp4",
        ]
        return prefix + canonical[:16]
    if stage == "stage1":
        return ["assets/series/recapture/raw/stage1-train1001-replay.mp4"] + canonical[:19]
    return [
        "assets/series/recapture/raw/stage2-single-batch-replay.mp4",
        "assets/series/recapture/raw/stage2-adapter-reload-replay.mp4",
    ] + canonical[:18]


def build_episode(root: Path, stage: str) -> dict[str, Any]:
    theme = THEMES[stage]
    static = STATIC_SOURCES[stage]
    segments: list[dict[str, Any]] = []
    for index, source in enumerate(_real_sources(root, stage), start=1):
        real_text = theme["real"][(index - 1) % len(theme["real"])]
        segments.append(
            {
                "segment_id": f"{stage}-长片-{index:02d}-实录",
                "source": source,
                "source_type": "real_recording",
                "evidence_ref": "experiments/exp02-equivalent-v3/eval_result.json" if "/canonical/" in source else "docs/evidence/2026-07-16-stage2-stage3-recapture-evidence.json",
                "duration_s": 24,
                "layout": "landscape",
                "narration": real_text,
                "subtitle": [real_text],
                "overlay": theme["overlay"],
                "preserve_source_overlay": "/canonical/" in source or "annotated" in source,
            }
        )
        static_source, source_type, evidence_ref = static[(index - 1) % len(static)]
        static_text = theme["static"][(index - 1) % len(theme["static"])]
        segments.append(
            {
                "segment_id": f"{stage}-长片-{index:02d}-解释",
                "source": static_source,
                "source_type": source_type,
                "evidence_ref": evidence_ref,
                "duration_s": 6,
                "layout": "landscape",
                "narration": static_text,
                "subtitle": [static_text],
                "overlay": theme["overlay"],
            }
        )
    return {"episode": stage, "title": theme["title"], "segments": segments}


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    return {
        "schema_version": "aima-vln-series/v1",
        "series_title": "GenieSim × StreamVLN 非官方等价适配深度教程",
        "status": "final_long_storyboard_ready",
        "real_ratio_target": 0.75,
        "metric_source": "experiments/exp02-equivalent-v3/eval_result.json",
        "episodes": [build_episode(root, f"stage{index}") for index in range(4)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "content/series/final-long-manifest.json")
    args = parser.parse_args()
    manifest = build_manifest(ROOT)
    args.output.resolve().write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
