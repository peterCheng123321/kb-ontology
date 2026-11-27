#!/usr/bin/env python3
"""把候选关联池与人工判定对齐并计数。

本版本仍把判定表写在代码里，不能从外部文件读取。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = REPO_ROOT / "review" / "v3_candidate_pool.json"
REV_DIR = REPO_ROOT / "review"
STATS_DIR = REPO_ROOT / "docs" / "stats"

# 内联判定表：link_id -> (判定, 理由)。外部文件尚未接入。
JUDGMENTS: dict[str, tuple[str, str]] = {}


def main() -> int:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    pool_by_id: dict[str, tuple[str, dict]] = {}
    for method, items in pool.items():
        for item in items:
            pool_by_id[item["link_id"]] = (method, item)

    reviewed_items = []
    by_method_counts: dict[str, Counter] = defaultdict(Counter)
    missing = []
    for link_id, (judgment, reason) in JUDGMENTS.items():
        if link_id not in pool_by_id:
            missing.append(link_id)
            continue
        method, meta = pool_by_id[link_id]
        by_method_counts[method][judgment] += 1
        reviewed_items.append(
            {
                "link_id": link_id,
                "method": method,
                "judgment": judgment,
                "reason": reason,
                "evidence": {key: value for key, value in meta.items() if key != "link_id"},
            }
        )
    if missing:
        print(f"WARNING: {len(missing)} judgment IDs not found in pool: {missing}", file=sys.stderr)

    payload = {
        "total_reviewed": len(reviewed_items),
        "overall_counts": dict(Counter(row["judgment"] for row in reviewed_items)),
        "by_method_counts": {method: dict(counter) for method, counter in sorted(by_method_counts.items())},
        "items": reviewed_items,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    REV_DIR.mkdir(parents=True, exist_ok=True)
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    (REV_DIR / "v3_review_samples.json").write_text(text, encoding="utf-8")
    (STATS_DIR / "v3-review.json").write_text(text, encoding="utf-8")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
