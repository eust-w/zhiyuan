"""Fail closed on local model inputs before importing external model code.

This is a file-format/path guard, not a dependency-CVE fix or a model sandbox.
Use trusted, immutable checkpoint directories and reviewed StreamVLN source.
Tensor content/shape validation remains the safetensors loader's responsibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _directory(directory: Path) -> Path:
    root = directory.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"model directory must already exist locally: {directory}")
    return root


def _local_file(root: Path, filename: str) -> Path:
    relative = Path(filename)
    if not filename or relative.is_absolute() or ".." in relative.parts or "\\" in filename:
        raise ValueError(f"model file must be a relative path inside its directory: {filename}")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"model file resolves outside its directory: {filename}") from exc
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"model file is missing or empty: {filename}")
    return path


def _json_object(root: Path, filename: str) -> dict[str, Any]:
    path = _local_file(root, filename)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"model JSON must contain an object: {filename}")
    return value


def _reject_pickle_files(root: Path) -> None:
    # The external vision/training loaders do not all expose use_safetensors.
    # Reject alternate pickle weights as well as bin-only checkpoints so they
    # cannot silently choose a fallback. Do not auto-convert untrusted pickle.
    for path in root.rglob("*"):
        if path.suffix.lower() in {".bin", ".pt", ".pth", ".pkl", ".pickle"}:
            raise ValueError(f"pickle weights are not permitted; use safetensors only: {path.name}")


def validate_model_directory(directory: Path) -> tuple[Path, ...]:
    """Check local config, single/sharded safetensors, and path containment."""
    root = _directory(directory)
    # Transformers 4.45.1 automatically detects PEFT metadata and may replace
    # this path with base_model_name_or_path before loading weights. Base and
    # vision directories must not redirect past the checks below. Adapters use
    # validate_adapter_directory separately.
    adapter_config = root / "adapter_config.json"
    if adapter_config.exists() or adapter_config.is_symlink():
        raise ValueError("adapter_config.json redirection is forbidden in base/vision model directories")
    _json_object(root, "config.json")
    _reject_pickle_files(root)
    weights: set[Path] = set()
    single = root / "model.safetensors"
    index = root / "model.safetensors.index.json"
    if single.exists() or single.is_symlink():
        weights.add(_local_file(root, single.name))
    if index.exists() or index.is_symlink():
        mapping = _json_object(root, index.name).get("weight_map")
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("safetensors index must contain a non-empty weight_map")
        for filename in mapping.values():
            if not isinstance(filename, str) or not filename.endswith(".safetensors"):
                raise ValueError("safetensors index may reference only .safetensors files")
            weights.add(_local_file(root, filename))
    if not weights:
        raise ValueError("local model.safetensors or a complete safetensors index is required")
    return tuple(sorted(weights))


def validate_adapter_directory(directory: Path) -> dict[str, Any]:
    """Require PEFT's local safe filename; never accept adapter_model.bin."""
    root = _directory(directory)
    config = _json_object(root, "adapter_config.json")
    # PEFT loads only these two weight names. Trainer metadata such as
    # training_args.bin may coexist, but is never read by this reload path.
    pickle_weight = root / "adapter_model.bin"
    if pickle_weight.exists() or pickle_weight.is_symlink():
        raise ValueError("pickle adapter weights are not permitted; use adapter_model.safetensors only")
    _local_file(root, "adapter_model.safetensors")
    return config


def resolve_vision_directory(base: Path, vision: Path | None = None) -> Path:
    """Resolve a caller override or the base config's local vision directory."""
    if vision is None:
        config = _json_object(_directory(base), "config.json")
        name = config.get("mm_vision_tower") or config.get("vision_tower")
        if not isinstance(name, str) or not name:
            raise ValueError("provide --vision or a local mm_vision_tower in config.json")
        vision = Path(name)
    root = _directory(vision)
    validate_model_directory(root)
    return root


def validate_training_vision_reference(base: Path, vision: Path) -> None:
    """Bind the base config's early-created tower to the checked CLI tower.

    StreamVLN constructs a tower from the base config before applying the CLI
    training arguments. Updating config later does not replace the tower's
    saved name. Reject drift; never rewrite the original checkpoint config.
    """
    config = _json_object(_directory(base), "config.json")
    expected = _directory(vision)
    selected = "mm_vision_tower" if "mm_vision_tower" in config else "vision_tower"
    selected_name = config.get(selected)
    if not isinstance(selected_name, str) or not selected_name.strip():
        raise ValueError(f"base config {selected} must name the validated local --vision directory")
    for field in ("mm_vision_tower", "vision_tower"):
        name = config.get(field)
        if name is None or name == "":
            continue
        # Training runs with cwd=the external repo; relative references could
        # resolve differently from this preflight and are therefore rejected.
        if not isinstance(name, str) or not Path(name).is_absolute():
            raise ValueError(f"base config {field} must be an absolute local vision path, not a remote or relative name")
        referenced = Path(name).resolve()
        if not referenced.is_dir() or referenced != expected:
            raise ValueError(f"base config {field} does not resolve to the validated --vision directory")


def vision_model_name(vision: Path) -> str:
    """Preserve StreamVLN's case-sensitive SigLIP dispatch without alias drift."""
    root = _directory(vision)
    validate_model_directory(root)
    if "siglip" in str(root):
        return str(root)
    alias = root.parent / "siglip-local"
    if alias.exists() or alias.is_symlink():
        if not alias.is_symlink() or alias.resolve() != root:
            raise ValueError("existing SigLIP alias does not point to the validated vision directory")
    else:
        alias.symlink_to(root, target_is_directory=True)
    return str(alias)
