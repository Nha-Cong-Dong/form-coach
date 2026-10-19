"""Kiểm tra chéo: file do code TypeScript của trang quay dựng ra phải qua được parse_session.

Gọi `node web/scripts/sample-session.ts` (Node ≥ 22.18 chạy thẳng TypeScript). Không có Node
phù hợp thì bỏ qua, vì phần Python vẫn được test riêng ở test_session_json.py.
"""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from formcoach.pose.session_json import load_session_json

SCRIPT = Path("web/scripts/sample-session.ts")


def _node() -> str | None:
    node = shutil.which("node")
    if node is None:
        return None
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    major, minor = (int(p) for p in version.strip().lstrip("v").split(".")[:2])
    return node if (major, minor) >= (22, 18) else None


NODE = _node()
pytestmark = pytest.mark.skipif(NODE is None, reason="cần Node ≥ 22.18 để chạy file .ts")


def test_typescript_session_passes_python_validation(tmp_path: Path) -> None:
    out = tmp_path / "from_ts.json"
    subprocess.run([NODE, str(SCRIPT), str(out)], check=True, capture_output=True)

    pose, meta = load_session_json(out)  # sai định dạng là SessionFormatError ở đây

    assert pose.keypoints.shape == (60, 33, 3)
    assert np.isnan(pose.keypoints[20]).all()  # khung không thấy người
    assert pose.frame_size == (1280, 720)
    assert meta.session_id == "2026-10-20T19-05-12_pushup"
    assert meta.set_errors == frozenset({"shallow"})
    assert meta.recorded_at.startswith("2026-10-20T19:05:12")
    assert meta.source == {
        "pose": "mediapipe-js",
        "version": "1.1.1",
        "model": "pose_landmarker_full",
    }
    assert (np.diff(meta.timestamps_ms) > 0).all()  # kể cả cặp khung cách nhau 0,04 ms
    assert pose.fps == pytest.approx(30, abs=3)
