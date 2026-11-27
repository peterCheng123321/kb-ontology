#!/usr/bin/env python3
"""把外部评审结论连接到候选关联池，并只把结果写到指定目录。"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "review"
PROTOCOL = "每类新增候选关联至多抽查 10 条，只依据官方或结构化字段。"
BASIS = "仅依据结构化或官方字段，不含消费者投诉原文。"

class InputError(Exception):
    """调用方可以修正的输入错误。"""

def read_json(path: Path, what: str) -> object:
    if not path.is_file():
        raise InputError(f"缺少{what}：{path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{what}不是合法 JSON：{exc.reason}") from exc
    except OSError as exc:
        raise InputError(f"无法读取{what}：{path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"{what}不是合法 JSON：{exc.msg}") from exc

def nonempty(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

def parse_judgments(doc: object) -> tuple[str, str, list[dict]]:
    if not isinstance(doc, dict):
        raise InputError("判定结构无效：顶层必须是对象")
    reviewer = nonempty(doc.get("reviewer"))
    reviewed_at = nonempty(doc.get("reviewed_at"))
    if reviewer is None:
        raise InputError("判定文件缺少评审人（reviewer）")
    if reviewed_at is None:
        raise InputError("判定文件缺少评审时间（reviewed_at）")
    rows = doc.get("judgments")
    if not isinstance(rows, list):
        raise InputError("判定结构无效：judgments 必须是数组")
    parsed: list[dict] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise InputError("判定结构无效：条目必须是对象")
        link_id = row.get("link_id")
        judgment = row.get("judgment")
        reason = row.get("reason")
        if not isinstance(link_id, str) or not link_id.strip():
            raise InputError("判定结构无效：条目缺少 link_id")
        if not isinstance(judgment, str) or not judgment.strip():
            raise InputError("判定结构无效：条目缺少 judgment")
        if not isinstance(reason, str):
            raise InputError("判定结构无效：条目缺少 reason")
        if link_id in seen:
            duplicates.append(link_id)
        seen.add(link_id)
        parsed.append({"link_id": link_id, "judgment": judgment, "reason": reason})
    if duplicates:
        raise InputError("判定中的 link_id 重复：" + "、".join(duplicates))
    return reviewer, reviewed_at, parsed

def index_pool(doc: object) -> dict[str, tuple[str, dict]]:
    if not isinstance(doc, dict):
        raise InputError("候选池结构无效：顶层必须是对象")
    indexed: dict[str, tuple[str, dict]] = {}
    duplicates: list[str] = []
    for method, items in doc.items():
        if not isinstance(method, str) or not isinstance(items, list):
            raise InputError("候选池结构无效：每个方法的值必须是数组")
        for item in items:
            if not isinstance(item, dict):
                raise InputError("候选池结构无效：条目必须是对象")
            link_id = item.get("link_id")
            if not isinstance(link_id, str) or not link_id.strip():
                raise InputError("候选池结构无效：条目缺少 link_id")
            if link_id in indexed:
                duplicates.append(link_id)
                continue
            indexed[link_id] = (method, item)
    if duplicates:
        raise InputError("候选池中的 link_id 重复：" + "、".join(duplicates))
    return indexed

def join_rows(rows: list[dict], pool_by_id: dict[str, tuple[str, dict]]) -> tuple[list[dict], list[str], dict[str, Counter]]:
    """每条判定只做一次字典查找。"""
    items: list[dict] = []
    missing: list[str] = []
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        found = pool_by_id.get(row["link_id"])
        if found is None:
            missing.append(row["link_id"])
            continue
        method, meta = found
        counts[method][row["judgment"]] += 1
        items.append({
            "link_id": row["link_id"],
            "method": method,
            "judgment": row["judgment"],
            "reason": row["reason"],
            "basis": BASIS,
            "evidence": {key: value for key, value in meta.items() if key != "link_id"},
        })
    return items, missing, counts

def shorten(evidence: dict) -> dict:
    out = {}
    for key, value in evidence.items():
        out[key] = value[:177] + "..." if isinstance(value, str) and len(value) > 180 else value
    return out

def repository_root(start: Path) -> Path | None:
    """从脚本位置向上找最近的 .git。没有 .git 就不是仓库。"""
    for parent in (start, *start.parents):
        if (parent / ".git").exists():
            return parent
    return None

def assert_output_dir_allowed(output_dir: Path) -> None:
    """仓库内只允许写到 review/ 之下。先解析符号链接和 ..，再创建目录。"""
    root = repository_root(Path(__file__).resolve())
    if root is None:
        return
    resolved = output_dir.resolve()
    review = (root / "review").resolve()
    if resolved.is_relative_to(root) and not resolved.is_relative_to(review):
        raise InputError(f"拒绝把输出写到仓库内 review/ 以外的目录：{output_dir}")

def write_outputs(output_dir: Path, full: dict, summary: dict) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise InputError(f"无法创建输出目录：{output_dir}") from exc
    root = output_dir.resolve()
    for name, payload in (("v3_review_samples.json", full), ("v3-review.json", summary)):
        dest = (root / name).resolve()
        if dest.parent != root:
            raise InputError(f"拒绝写入输出目录之外的路径：{name}")
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="把外部评审结论连接到候选关联池并写出计数。")
    parser.add_argument("--pool", type=Path, help="候选池 JSON，默认 review/v3_candidate_pool.json")
    parser.add_argument("--judgments", type=Path, help="判定 JSON，默认 review/v3_judgments.json")
    parser.add_argument("--output-dir", type=Path, help="输出目录，默认 review/")
    args = parser.parse_args(argv)
    judgments_path = args.judgments or (REVIEW_DIR / "v3_judgments.json")
    pool_path = args.pool or (REVIEW_DIR / "v3_candidate_pool.json")
    output_dir = args.output_dir or REVIEW_DIR
    try:
        assert_output_dir_allowed(output_dir)
        reviewer, reviewed_at, rows = parse_judgments(read_json(judgments_path, "判定文件"))
        items, missing, counts = join_rows(rows, index_pool(read_json(pool_path, "候选池文件")))
        full = {
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "protocol": PROTOCOL,
            "total_reviewed": len(items),
            "overall_counts": dict(Counter(item["judgment"] for item in items)),
            "by_method_counts": {method: dict(counter) for method, counter in sorted(counts.items())},
            "items": items,
        }
        write_outputs(output_dir, full, {**full, "items": [{**item, "evidence": shorten(item["evidence"])} for item in items]})
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已连接 {len(items)} 条，输出目录 {output_dir}")
    if missing:
        print("以下判定编号不在候选池中：" + "、".join(missing), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
