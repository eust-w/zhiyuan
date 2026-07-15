"""Validate the four platform-native draft packages before a user publishes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE = re.compile(r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\d{1,3}\.){3}\d{1,3}|__REDACTED_CREDENTIAL_LITERAL__)", re.I)
FORBIDDEN = ("个人实验", "官方适配", "课程原样复现", "榜单成绩")


def section(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end in body else body


def build_report(root: Path = ROOT, article_root: Path | None = None) -> dict[str, object]:
    article_root = article_root or root / "article/series"
    errors: list[str] = []
    files: dict[str, dict[str, int]] = {}
    for stage in ("stage0", "stage1", "stage2", "stage3"):
        paths = {
            "bilibili": article_root / f"bilibili-{stage}.md",
            "zhihu": article_root / f"zhihu-{stage}.md",
            "xiaohongshu": article_root / f"xiaohongshu-{stage}.md",
            "douyin": article_root / f"douyin-{stage}.md",
        }
        files[stage] = {}
        for platform, path in paths.items():
            if not path.is_file():
                errors.append(f"missing {path.relative_to(root)}")
                continue
            text = path.read_text(encoding="utf-8")
            files[stage][platform] = len(text)
            if any(token in text for token in FORBIDDEN):
                errors.append(f"forbidden wording in {path.name}")
            if SENSITIVE.search(text):
                errors.append(f"sensitive content in {path.name}")
            if platform == "bilibili":
                desc = section(text, "## 投稿简介\n", "\n## 标签")
                if not 800 <= len(desc) <= 1200:
                    errors.append(f"bilibili description length {len(desc)} in {path.name}")
            elif platform == "zhihu" and not 3000 <= len(text) <= 5000:
                errors.append(f"zhihu length {len(text)} in {path.name}")
            elif platform == "xiaohongshu":
                body = section(text, "## 正文（建议 800–1000 字，发布前按最终图片微调）\n", "\n## 避坑清单")
                if not 800 <= len(body) <= 1000:
                    errors.append(f"xiaohongshu body length {len(body)} in {path.name}")
            elif platform == "douyin" and text.count(". ") < 3:
                errors.append(f"douyin title candidates missing in {path.name}")
    return {"status": "passed" if not errors else "failed", "errors": errors, "files": files}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-root", type=Path, default=ROOT / "article/series")
    parser.add_argument("--output", type=Path, default=ROOT / "content/series/platform-acceptance.json")
    args = parser.parse_args()
    report = build_report(ROOT, args.article_root.resolve())
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
