"""Evidence and public-copy contract for the navigation challenge video."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


FORBIDDEN_PUBLIC_TERMS = (
    "课程",
    "PDF",
    "指南",
    "私有包",
    "原样复现",
    "等价适配",
    "非官方适配",
)

APPROVED_CERTIFICATE_COPY = (
    "完成 baseline 并通过实际验收后，可按活动规则申请智元认证证书；"
    "创新成果的算力、技术辅导或展示资源，以主办方实际审核和通知为准。"
)

_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "email",
        re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    ),
    (
        "ipv4",
        re.compile(
            r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
        ),
    ),
    (
        "mac_absolute_path",
        re.compile(r"(?<![\w.-])/Users/[^\s\"'，。；]+"),
    ),
    (
        "linux_root_path",
        re.compile(r"(?<![\w.-])/root/[^\s\"'，。；]+"),
    ),
    (
        "ssh_command",
        re.compile(r"(?im)(?:^|[\s；;])ssh(?:\s+-\S+)*\s+\S+"),
    ),
    (
        "credential_label",
        re.compile(
            r"(?i)(?:password|passwd|token|secret|api[_ -]?key|"
            r"密码|口令|密钥|验证码)\s*[:：=]\s*\S+"
        ),
    ),
    (
        "instance_id",
        re.compile(
            r"(?i)(?:instance[_ -]?id|实例(?:编号|ID|id))\s*[:：=]\s*[A-Za-z0-9._-]+"
        ),
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _safe_episode_detail(summary: dict[str, Any]) -> list[dict[str, Any]]:
    safe_fields = (
        "episode_id",
        "success_0_5",
        "success_3",
        "oracle_success_0_5",
        "oracle_success_3",
        "final_distance_to_goal",
        "min_distance_to_goal",
        "path_length",
        "shortest_path_length",
        "spl_0_5",
        "spl_3",
        "steps",
        "collisions",
        "truncated",
        "action_counts",
    )
    details = summary.get("episodes_detail", [])
    if not isinstance(details, list):
        raise ValueError("model summary episodes_detail must be a list")
    return [
        {field: episode[field] for field in safe_fields if field in episode}
        for episode in details
        if isinstance(episode, dict)
    ]


def _variant_snapshot(evaluation: dict[str, Any]) -> dict[str, Any]:
    summary = evaluation.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("model evaluation summary must be an object")
    required = (
        "episodes",
        "success_0_5",
        "success_3",
        "oracle_success_0_5",
        "oracle_success_3",
        "collisions",
        "mean_final_distance_to_goal",
        "mean_min_distance_to_goal",
        "mean_path_length",
        "mean_spl_0_5",
        "mean_spl_3",
        "mean_steps",
    )
    missing = [field for field in required if field not in summary]
    if missing:
        raise ValueError(f"model summary missing fields: {', '.join(missing)}")
    snapshot = {field: summary[field] for field in required}
    snapshot["episodes_detail"] = _safe_episode_detail(summary)
    snapshot["collisions_meaning"] = "安全门拦截的前进尝试"
    return snapshot


def evidence_snapshot(root: Path) -> dict[str, Any]:
    """Return a shareable fact snapshot built only from authoritative evidence."""

    root = root.resolve()
    experiment = root / "experiments/exp02-equivalent-v3"
    evaluation = _load_json(experiment / "eval_result.json")
    training = _load_json(experiment / "stage2_result_v2.json")
    dataset = _load_json(experiment / "dataset-validation.json")
    health = _load_json(experiment / "stage0-health.json")

    root_ids = evaluation.get("heldout_episode_ids")
    if evaluation.get("same_heldout_batch") is not True:
        raise ValueError("eval_result must declare the same held-out batch")
    if not isinstance(root_ids, list) or len(root_ids) != 10 or len(set(root_ids)) != 10:
        raise ValueError("eval_result must contain ten unique held-out episode IDs")

    evaluations: dict[str, dict[str, Any]] = {}
    for public_name, source_name in (("base", "base_model"), ("lora", "lora_model")):
        container = evaluation.get(source_name)
        if not isinstance(container, dict):
            raise ValueError(f"eval_result missing {source_name}")
        model_evaluation = container.get("model_evaluation")
        if not isinstance(model_evaluation, dict):
            raise ValueError(f"{source_name} missing model_evaluation")
        if model_evaluation.get("same_heldout_batch") is not True:
            raise ValueError(f"{source_name} must declare the same held-out batch")
        if model_evaluation.get("episode_ids") != root_ids:
            raise ValueError("Base and LoRA must use identical ordered held-out episode IDs")
        detail_ids = [
            item.get("episode_id")
            for item in model_evaluation.get("summary", {}).get("episodes_detail", [])
            if isinstance(item, dict)
        ]
        if detail_ids != root_ids:
            raise ValueError(f"{source_name} detail rows must match ordered held-out episode IDs")
        evaluations[public_name] = _variant_snapshot(model_evaluation)

    full_training = training.get("gates", {}).get("full_training", {})
    adapter_reload = training.get("gates", {}).get("adapter_reload", {})
    if not isinstance(full_training, dict):
        raise ValueError("stage2 result missing full_training gate")
    if full_training.get("nan_or_inf") is not False:
        raise ValueError("LoRA training contains NaN or Inf")
    peak_mib = full_training.get("peak_gpu_memory_mib")
    if not isinstance(peak_mib, (int, float)):
        raise ValueError("LoRA training missing peak GPU memory")

    train_split = dataset.get("train", {})
    eval_split = dataset.get("eval", {})
    if (
        train_split.get("valid") != train_split.get("episodes")
        or eval_split.get("valid") != eval_split.get("episodes")
        or train_split.get("invalid") != 0
        or eval_split.get("invalid") != 0
    ):
        raise ValueError("dataset validation must have no invalid episodes")

    return {
        "schema_version": "geniesim-streamvln-challenge-facts/v1",
        "metric_source": "experiments/exp02-equivalent-v3/eval_result.json",
        "training_source": "experiments/exp02-equivalent-v3/stage2_result_v2.json",
        "dataset_source": "experiments/exp02-equivalent-v3/dataset-validation.json",
        "heldout_episode_ids": list(root_ids),
        "same_heldout_batch": True,
        "scene": health.get("scene"),
        "robot": health.get("robot"),
        "camera": health.get("camera"),
        "dataset": {
            "smoke_episodes": 3,
            "train_episodes": train_split.get("episodes"),
            "heldout_episodes": eval_split.get("episodes"),
        },
        "lora_training": {
            "updates": full_training.get("observed_steps"),
            "loss_first": full_training.get("loss_first"),
            "loss_last": full_training.get("loss_last"),
            "grad_norm_max": full_training.get("grad_norm_max"),
            "peak_gpu_memory_mib": peak_mib,
            "peak_gpu_memory_gib": peak_mib / 1024,
            "nan_or_inf": full_training.get("nan_or_inf"),
            "adapter_reload_passed": adapter_reload.get("status") == "passed",
            "config": training.get("config", {}),
        },
        "base": evaluations["base"],
        "lora": evaluations["lora"],
    }


def scan_public_text(text: str) -> list[str]:
    """Return forbidden public terms in stable declaration order."""

    return [term for term in FORBIDDEN_PUBLIC_TERMS if term in text]


def scan_sensitive_text(text: str) -> list[str]:
    """Return labeled sensitive-data matches without echoing their values."""

    hits: list[str] = []
    for label, pattern in _SENSITIVE_PATTERNS:
        for _match in pattern.finditer(text):
            hits.append(label)
    return hits


def scan_public_bundle(value: Any, path: str = "$") -> list[str]:
    """Recursively scan a JSON-compatible public content bundle."""

    hits: list[str] = []
    if isinstance(value, str):
        hits.extend(f"{path}: forbidden:{term}" for term in scan_public_text(value))
        hits.extend(f"{path}: sensitive:{label}" for label in scan_sensitive_text(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            hits.extend(scan_public_bundle(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(scan_public_bundle(item, f"{path}[{index}]"))
    return hits


def validate_claims(text: str) -> list[str]:
    """Reject unconditional certificate or resource promises."""

    errors: list[str] = []
    conditional = any(
        marker in text
        for marker in ("可按", "可申请", "有机会", "可能", "以主办方", "以实际", "审核")
    )
    guaranteed = any(
        marker in text
        for marker in ("保证获得", "必得", "一定获得", "直接获得", "完成后获得", "即可获得")
    )
    if "证书" in text and guaranteed and not conditional:
        errors.append("certificate claim must be conditional")
    resource_guaranteed = any(
        marker in text for marker in ("保证提供资源", "一定提供资源", "直接获得资源")
    )
    if resource_guaranteed and not conditional:
        errors.append("resource claim must be conditional")
    return errors


def public_repo_path(path: Path, root: Path) -> str:
    """Return a POSIX repository-relative path or reject an escaping path."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("public path must stay inside repository root") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
