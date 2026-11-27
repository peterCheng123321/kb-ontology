"""VSSo 许可、说明文档与 Makefile 目标。"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
R = Path(__file__).resolve().parents[1]
def _make(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["make", *args], cwd=R, capture_output=True, text=True, check=False)
def test_notice_vsso_uses_w3c_document_license() -> None:
    text = (R / "NOTICE").read_text(encoding="utf-8")
    assert "W3C Document License" in text and "https://www.w3.org/Consortium/Legal/copyright-documents" in text
    assert "https://github.com/w3c/vsso/blob/gh-pages/LICENSE.md" in text
    assert not any("VSSo" in line and ("CC" in line or "Apache" in line) for line in text.splitlines())
def test_readme_explains_offline_pytest() -> None:
    text = (R / "README.md").read_text(encoding="utf-8")
    assert "pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q" in text
    assert "候选池生成器不在本仓库" in text
def test_make_dry_run_lists_gen_and_pytest() -> None:
    gen, test = _make("-n", "gen"), _make("-n", "test")
    assert gen.returncode == 0 and "gen-shacl" in gen.stdout and test.returncode == 0 and "pytest -q" in test.stdout
test_make_dry_run_lists_gen_and_pytest = pytest.mark.skipif(
    shutil.which("make") is None, reason="make 不在 PATH",
)(test_make_dry_run_lists_gen_and_pytest)
def test_make_test_missing_interpreter_errors() -> None:
    result = _make("test", "PY=/nonexistent/python-b8")
    assert result.returncode != 0 and "找不到" in result.stderr + result.stdout
test_make_test_missing_interpreter_errors = pytest.mark.skipif(
    shutil.which("make") is None, reason="make 不在 PATH",
)(test_make_test_missing_interpreter_errors)

def test_make_checks_skip_when_make_missing(tmp_path: Path) -> None:
    """机器上没有 make 时，两条 make 检查应跳过，而不是失败。"""
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rs", "-q",
         "tests/test_project_surface.py::test_make_dry_run_lists_gen_and_pytest",
         "tests/test_project_surface.py::test_make_test_missing_interpreter_errors"],
        cwd=R, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "make 不在 PATH" in result.stdout + result.stderr
