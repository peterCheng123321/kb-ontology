"""v3_apply_review 从外部判定文件计数的行为测试。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "v3_apply_review.py"
FIXTURES = ROOT / "tests" / "fixtures" / "review"
REVIEWER = "fixture-reviewer"
REVIEWED_AT = "2026-01-01T00:00:00Z"
ACCEPTED = {"link_id": "link-alpha-001", "judgment": "accepted", "reason": "合成通过"}

def execute(script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, encoding="utf-8", env=env, check=False,
    )

def run_raw(directory: Path, pool: object, body: object) -> tuple[subprocess.CompletedProcess[str], Path]:
    directory.mkdir(parents=True, exist_ok=True)
    pool_path, judgments_path, out = directory / "pool.json", directory / "judgments.json", directory / "out"
    pool_path.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    judgments_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    args = ["--pool", str(pool_path), "--judgments", str(judgments_path), "--output-dir", str(out)]
    return execute(SCRIPT, args), out

def judged(rows: list[dict], reviewer: str | None = REVIEWER, reviewed_at: str | None = REVIEWED_AT) -> dict:
    body: dict = {"judgments": rows}
    if reviewer is not None:
        body["reviewer"] = reviewer
    if reviewed_at is not None:
        body["reviewed_at"] = reviewed_at
    return body

def one_pool() -> dict:
    return {"family_alpha": [{"link_id": "link-alpha-001", "note": "synthetic-a"}]}

def samples(out: Path) -> dict:
    return json.loads((out / "v3_review_samples.json").read_text(encoding="utf-8"))

def assert_rejected(result: subprocess.CompletedProcess[str], out: Path, needle: str) -> None:
    assert result.returncode != 0 and needle in result.stderr and not out.exists()

def stage_repo(tmp_path: Path) -> tuple[Path, Path]:
    layout = tmp_path / "repo"
    (layout / "scripts").mkdir(parents=True)
    stats = layout / "docs" / "stats"
    stats.mkdir(parents=True)
    (stats / "keep.txt").write_text("unchanged\n", encoding="utf-8")
    dest = layout / "scripts" / "v3_apply_review.py"
    shutil.copy(SCRIPT, dest)
    return layout, dest

def docs_text(layout: Path) -> dict[str, str]:
    docs = layout / "docs"
    return {str(path.relative_to(docs)): path.read_text(encoding="utf-8") for path in docs.rglob("*") if path.is_file()}

def fixture_pair() -> tuple[object, object]:
    pool = json.loads((FIXTURES / "pool.json").read_text(encoding="utf-8"))
    body = json.loads((FIXTURES / "judgments.json").read_text(encoding="utf-8"))
    return pool, body

def test_reads_judgments_from_external_file(tmp_path: Path) -> None:
    result, out = run_raw(tmp_path, *fixture_pair())
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = samples(out)
    assert payload["reviewer"] == REVIEWER and payload["reviewed_at"] == REVIEWED_AT
    assert payload["total_reviewed"] == 3
    assert payload["overall_counts"] == {"accepted": 1, "uncertain": 1, "rejected": 1}
    assert payload["by_method_counts"] == {
        "family_alpha": {"accepted": 1, "uncertain": 1},
        "family_beta": {"rejected": 1},
    }
    item = next(row for row in payload["items"] if row["link_id"] == "link-alpha-001")
    assert item["method"] == "family_alpha" and item["judgment"] == "accepted"
    assert item["reason"] == "合成通过" and item["evidence"] == {"note": "synthetic-a"} and item["basis"]
    summary = json.loads((out / "v3-review.json").read_text(encoding="utf-8"))
    assert summary["overall_counts"] == payload["overall_counts"]

def test_missing_judgments_file_exits_nonzero(tmp_path: Path) -> None:
    pool_path, out = tmp_path / "pool.json", tmp_path / "out"
    pool_path.write_text(json.dumps(one_pool()), encoding="utf-8")
    missing = tmp_path / "missing-judgments.json"
    result = execute(SCRIPT, ["--pool", str(pool_path), "--judgments", str(missing), "--output-dir", str(out)])
    assert_rejected(result, out, "缺少判定文件")

def test_missing_pool_file_exits_nonzero(tmp_path: Path) -> None:
    judgments_path, out = tmp_path / "judgments.json", tmp_path / "out"
    judgments_path.write_text(json.dumps(judged([ACCEPTED]), ensure_ascii=False), encoding="utf-8")
    missing = tmp_path / "missing-pool.json"
    result = execute(SCRIPT, ["--pool", str(missing), "--judgments", str(judgments_path), "--output-dir", str(out)])
    assert_rejected(result, out, "缺少候选池文件")

def test_judgments_without_reviewer_rejected(tmp_path: Path) -> None:
    cases = [
        (judged([ACCEPTED], reviewer=None), "评审人"),
        (judged([ACCEPTED], reviewer="   "), "评审人"),
        (judged([ACCEPTED], reviewed_at=None), "评审时间"),
    ]
    for index, (body, needle) in enumerate(cases):
        result, out = run_raw(tmp_path / str(index), one_pool(), body)
        assert_rejected(result, out, needle)

def test_unknown_link_ids_reported(tmp_path: Path) -> None:
    rows = [ACCEPTED, {"link_id": "link-missing-999", "judgment": "rejected", "reason": "合成缺失"}]
    result, out = run_raw(tmp_path, one_pool(), judged(rows))
    assert result.returncode != 0 and "link-missing-999" in result.stderr
    payload = samples(out)
    assert payload["total_reviewed"] == 1 and payload["overall_counts"] == {"accepted": 1}
    assert [row["link_id"] for row in payload["items"]] == ["link-alpha-001"]

def test_never_writes_tracked_paths(tmp_path: Path) -> None:
    layout, script = stage_repo(tmp_path)
    pool, body = fixture_pair()
    work = layout / "inputs"
    work.mkdir()
    (work / "pool.json").write_text(json.dumps(pool), encoding="utf-8")
    (work / "judgments.json").write_text(json.dumps(body), encoding="utf-8")
    given = layout / "given-out"
    before_docs, before_files = docs_text(layout), {path.relative_to(layout) for path in layout.rglob("*") if path.is_file()}
    result = execute(script, ["--pool", str(work / "pool.json"), "--judgments", str(work / "judgments.json"), "--output-dir", str(given)])
    new_files = {path.relative_to(layout) for path in layout.rglob("*") if path.is_file()} - before_files
    assert result.returncode == 0, result.stderr
    assert docs_text(layout) == before_docs and new_files and all(path.parts[0] == "given-out" for path in new_files)

def _corrupt(tmp_path: Path, name: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    pool_path, judgments_path, out = tmp_path / "pool.json", tmp_path / "judgments.json", tmp_path / "out"
    pool_path.write_text(json.dumps(one_pool()) if name != "pool" else "{", encoding="utf-8")
    judgments_path.write_text(
        json.dumps(judged([ACCEPTED]), ensure_ascii=False) if name != "judgments" else "{",
        encoding="utf-8",
    )
    args = ["--pool", str(pool_path), "--judgments", str(judgments_path), "--output-dir", str(out)]
    return execute(SCRIPT, args), out

def test_malformed_judgments_json_exits_nonzero(tmp_path: Path) -> None:
    result, out = _corrupt(tmp_path, "judgments")
    assert_rejected(result, out, "不是合法 JSON")

def test_malformed_pool_json_exits_nonzero(tmp_path: Path) -> None:
    result, out = _corrupt(tmp_path, "pool")
    assert_rejected(result, out, "不是合法 JSON")

def test_invalid_structure_rejected(tmp_path: Path) -> None:
    result, out = run_raw(tmp_path / "pool", [], judged([ACCEPTED]))
    assert_rejected(result, out, "候选池结构无效")
    body = {"reviewer": REVIEWER, "reviewed_at": REVIEWED_AT, "judgments": {}}
    result, out = run_raw(tmp_path / "judgments", one_pool(), body)
    assert_rejected(result, out, "判定结构无效")

def test_empty_judgments_zero_counts(tmp_path: Path) -> None:
    result, out = run_raw(tmp_path, one_pool(), judged([]))
    assert result.returncode == 0 and result.stderr == "", result.stderr
    payload = samples(out)
    assert payload["total_reviewed"] == 0 and payload["items"] == []
    assert payload["overall_counts"] == {} and payload["by_method_counts"] == {}

def test_duplicate_link_ids_rejected(tmp_path: Path) -> None:
    rows = [ACCEPTED, {"link_id": "link-alpha-001", "judgment": "rejected", "reason": "合成重复"}]
    result, out = run_raw(tmp_path, one_pool(), judged(rows))
    assert_rejected(result, out, "重复")
    assert "link-alpha-001" in result.stderr

def test_large_pool_lookup_stays_fast(tmp_path: Path) -> None:
    pool_size, judgment_count = 40000, 4000
    items = [{"link_id": f"id-{index:05d}", "n": index} for index in range(pool_size)]
    start = pool_size - judgment_count
    rows = [{"link_id": f"id-{index:05d}", "judgment": "accepted", "reason": "合成批量"} for index in range(start, pool_size)]
    started = time.perf_counter()
    result, out = run_raw(tmp_path, {"family_alpha": items}, judged(rows))
    assert result.returncode == 0, result.stderr
    assert samples(out)["total_reviewed"] == judgment_count and time.perf_counter() - started < 1.5

def test_run_twice_identical_output(tmp_path: Path) -> None:
    result, out = run_raw(tmp_path, *fixture_pair())
    assert result.returncode == 0, result.stderr
    full_bytes = (out / "v3_review_samples.json").read_bytes()
    summary_bytes = (out / "v3-review.json").read_bytes()
    again, _out = run_raw(tmp_path, *fixture_pair())
    assert again.returncode == 0
    assert (out / "v3_review_samples.json").read_bytes() == full_bytes
    assert (out / "v3-review.json").read_bytes() == summary_bytes

def test_summary_truncates_long_evidence(tmp_path: Path) -> None:
    kept, long = "k" * 180, "x" * 181
    pool = {"family_alpha": [{"link_id": "link-keep-001", "note": kept}, {"link_id": "link-long-001", "note": long}]}
    rows = [
        {"link_id": "link-keep-001", "judgment": "accepted", "reason": "合成短"},
        {"link_id": "link-long-001", "judgment": "accepted", "reason": "合成长"},
    ]
    result, out = run_raw(tmp_path, pool, judged(rows))
    assert result.returncode == 0, result.stderr
    full = {row["link_id"]: row["evidence"]["note"] for row in samples(out)["items"]}
    summary = {row["link_id"]: row["evidence"]["note"] for row in json.loads((out / "v3-review.json").read_text())["items"]}
    assert full["link-keep-001"] == kept and summary["link-keep-001"] == kept
    assert full["link-long-001"] == long and summary["link-long-001"] == ("x" * 177) + "..."

def test_pool_duplicate_link_id_same_family_rejected(tmp_path: Path) -> None:
    """同一方法里 link_id 出现两次时拒绝，且不写文件。"""
    pool = {"family_alpha": [
        {"link_id": "link-alpha-001", "note": "first"},
        {"link_id": "link-alpha-001", "note": "second"},
    ]}
    result, out = run_raw(tmp_path, pool, judged([ACCEPTED]))
    assert result.returncode == 1
    assert "候选池" in result.stderr and "重复" in result.stderr and "link-alpha-001" in result.stderr
    assert not out.exists()


def test_pool_duplicate_link_id_across_families_rejected(tmp_path: Path) -> None:
    """不同方法里出现同一个 link_id 时拒绝，且不写文件。"""
    pool = {
        "family_alpha": [{"link_id": "link-alpha-001", "note": "a"}],
        "family_beta": [{"link_id": "link-alpha-001", "note": "b"}],
    }
    result, out = run_raw(tmp_path, pool, judged([ACCEPTED]))
    assert result.returncode == 1
    assert "候选池" in result.stderr and "重复" in result.stderr and "link-alpha-001" in result.stderr
    assert not out.exists()


def _git_copy(tmp_path: Path) -> tuple[Path, Path]:
    layout = tmp_path / "repo"
    (layout / "scripts").mkdir(parents=True)
    stats = layout / "docs" / "stats"
    stats.mkdir(parents=True)
    (stats / "keep.txt").write_text("unchanged\n", encoding="utf-8")
    script = layout / "scripts" / "v3_apply_review.py"
    shutil.copy(SCRIPT, script)
    subprocess.run(["git", "init", "-q"], cwd=layout, check=True)
    return layout, script


def _run_in(script: Path, output: str, pool_path: Path, judgments_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), "--pool", str(pool_path), "--judgments", str(judgments_path), "--output-dir", output],
        capture_output=True, text=True, encoding="utf-8", env=env, check=False, cwd=cwd,
    )


def test_output_dir_inside_repo_outside_review_refused(tmp_path: Path) -> None:
    """仓库内除 review/ 以外的输出目录（含 ..、符号链接和仓库根）一律拒绝。"""
    layout, script = _git_copy(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    pool_path, judgments_path = inputs / "pool.json", inputs / "judgments.json"
    pool_path.write_text(json.dumps(one_pool()), encoding="utf-8")
    judgments_path.write_text(json.dumps(judged([ACCEPTED]), ensure_ascii=False), encoding="utf-8")
    keep = layout / "docs" / "stats" / "keep.txt"
    before, docs_before = keep.read_bytes(), {path.relative_to(layout) for path in (layout / "docs").rglob("*")}
    link = layout / "via-docs"
    link.symlink_to(layout / "docs" / "stats", target_is_directory=True)
    refused = [
        str(layout / "docs" / "stats"),
        "docs/stats",
        "review/../docs/stats",
        str(layout),
        ".",
        "not-review-new",
        str(link),
    ]
    for output in refused:
        result = _run_in(script, output, pool_path, judgments_path, layout)
        assert result.returncode == 1 and "拒绝" in result.stderr, (output, result.returncode, result.stderr)
        assert keep.read_bytes() == before
        assert not (layout / "not-review-new").exists()
        assert not (layout / "docs" / "stats" / "v3_review_samples.json").exists()
    assert {path.relative_to(layout) for path in (layout / "docs").rglob("*")} == docs_before
    allowed = _run_in(script, str(layout / "review" / "x"), pool_path, judgments_path, layout)
    assert allowed.returncode == 0, allowed.stderr
    assert (layout / "review" / "x" / "v3_review_samples.json").is_file()
    assert keep.read_bytes() == before


def test_gitignore_review_is_root_anchored(tmp_path: Path) -> None:
    """只忽略仓库根的 review/，不忽略嵌套的 tests/fixtures/review/。"""
    if shutil.which("git") is None:
        pytest.skip("git 不在 PATH 上")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    shutil.copy(ROOT / ".gitignore", repo / ".gitignore")
    (repo / "review").mkdir()
    (repo / "review" / "v3_judgments.json").write_text("{}\n", encoding="utf-8")
    nested = repo / "tests" / "fixtures" / "review"
    nested.mkdir(parents=True)
    (nested / "new_case.json").write_text("{}\n", encoding="utf-8")

    def check(relative: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "check-ignore", "--no-index", relative],
            cwd=repo, capture_output=True, text=True, check=False,
        )

    assert check("review/v3_judgments.json").returncode == 0
    assert check("tests/fixtures/review/new_case.json").returncode != 0


def test_default_paths_stay_inside_review_dir(tmp_path: Path) -> None:
    layout, script = stage_repo(tmp_path)
    review = layout / "review"
    review.mkdir()
    shutil.copy(FIXTURES / "pool.json", review / "v3_candidate_pool.json")
    shutil.copy(FIXTURES / "judgments.json", review / "v3_judgments.json")
    before = docs_text(layout)
    result = execute(script, [])
    assert result.returncode == 0, result.stderr
    payload = json.loads((review / "v3_review_samples.json").read_text(encoding="utf-8"))
    assert payload["total_reviewed"] == 3 and docs_text(layout) == before
    assert not (layout / "docs" / "stats" / "v3-review.json").exists()
