"""Chạy kiểm tra hàm định dạng trang kết quả (web/src/results/format.ts) bằng Node.

Cùng cách với test_web_format.py: Node ≥ 22.18 chạy thẳng TypeScript; không có thì bỏ qua.
"""

import subprocess
from pathlib import Path

import pytest

from tests.test_web_format import NODE

SCRIPT = Path("web/scripts/check-result-format.ts")

pytestmark = pytest.mark.skipif(NODE is None, reason="cần Node ≥ 22.18 để chạy file .ts")


def test_result_format_logic() -> None:
    result = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "check-result-format: ok" in result.stdout
