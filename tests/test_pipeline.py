import json
from pathlib import Path

import numpy as np
import pytest

from formcoach.__main__ import main
from formcoach.exercises import PushUp
from formcoach.pipeline import analyze, frame_timing, load_source
from tests.synthetic import make_session


def five_rep_session_elbow() -> np.ndarray:
    """Giữ plank 1 s → 5 rep (165° ↔ 70°, 2,4 s/rep) → giữ plank 1 s."""
    t = np.arange(int(5 * 2.4 * 30)) / 30
    reps = 117.5 + 47.5 * np.cos(2 * np.pi * t / 2.4)
    return np.concatenate([np.full(30, 165.0), reps, np.full(30, 165.0)])


def five_rep_session() -> dict:
    """Như file trang quay: giữ plank 1 s → 5 rep → giữ plank 1 s."""
    return make_session(five_rep_session_elbow(), jitter_ms=8.0)


@pytest.fixture
def session_file(tmp_path: Path) -> Path:
    path = tmp_path / "s.json"
    path.write_text(json.dumps(five_rep_session()), encoding="utf-8")
    return path


def test_analyze_counts_reps(session_file: Path) -> None:
    src = load_source(session_file)
    assert isinstance(src.exercise, PushUp)
    assert src.meta is not None
    assert src.times_s[0] == 0.0 and src.times_s[-1] > 13
    features, reps = analyze(src.pose, src.exercise)
    assert len(reps) == 5
    assert "elbow_angle" in features.signals


def test_frame_timing() -> None:
    t = np.array([0, 33, 66, 100, 133, 633, 666])  # một lần khựng 500 ms
    tm = frame_timing(t)
    assert tm.median_ms == pytest.approx(33)
    assert tm.max_ms == 500
    assert tm.long_gaps == 1
    assert tm.jitter_ratio > 1  # có khựng thì lệch chuẩn lớn hơn cả trung vị


def test_frame_timing_regular() -> None:
    tm = frame_timing(np.arange(0, 3000, 33.3))
    assert tm.jitter_ratio < 0.01
    assert tm.long_gaps == 0


def test_cli_analyze(session_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["analyze", str(session_file)])
    out = capsys.readouterr().out
    assert "Đếm được 5 rep" in out
    assert "Khoảng cách khung" in out
    assert "rep 5:" in out and "rep 6:" not in out


def test_cli_analyze_plot(session_file: Path, tmp_path: Path) -> None:
    main(["analyze", str(session_file), "--plot", "--out", str(tmp_path / "plots")])
    png = tmp_path / "plots" / "s_signals.png"
    assert png.exists() and png.stat().st_size > 10_000


def test_cli_requires_command() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cli_prints_rule_predictions_against_saved_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # File đặt đúng cấu trúc <data>/sessions/pushup/ và có nhãn đã lưu → so luật với nhãn.
    import dataclasses

    from formcoach.labels import default_labels, save_labels
    from formcoach.pose.session_json import parse_session

    data = make_session(five_rep_session_elbow(), jitter_ms=8.0)
    folder = tmp_path / "sessions" / "pushup"
    folder.mkdir(parents=True)
    path = folder / f"{data['session_id']}.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    pose, meta = parse_session(data)
    _, reps = analyze(pose, PushUp())
    times = (meta.timestamps_ms - meta.timestamps_ms[0]) / 1000
    labels = default_labels(meta.session_id, "pushup", reps, times, frozenset({"shallow"}),
                            PushUp().phase_thresholds())  # fmt: skip
    first, second, third, *rest = labels.reps
    second = dataclasses.replace(second, valid=False, errors=frozenset())
    third = dataclasses.replace(third, errors=frozenset({"shallow", "hip_sag"}))
    save_labels(dataclasses.replace(labels, reps=(first, second, third, *rest)), tmp_path)

    main(["analyze", str(path)])
    out = capsys.readouterr().out
    assert "chưa có luật cho: hip_sag" in out
    # Khuỷu xuống tới 70° > 67° → luật bắt shallow, khớp với nhãn.
    assert "rep 1: luật shallow | nhãn shallow  khớp" in out
    assert "rep 2: luật shallow | nhãn: không phải rep" in out
    # hip_sag chưa có luật: không so, và phải nói rõ thay vì chỉ ghi "khớp".
    assert (
        "rep 3: luật shallow | nhãn hip_sag, shallow  khớp (không so hip_sag: chưa có luật)" in out
    )
    assert "khớp hoàn toàn 4/4 rep" in out


def test_cli_without_labels_still_prints_rules(
    session_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["analyze", str(session_file)])
    out = capsys.readouterr().out
    assert "Lỗi theo luật:" in out and "khớp hoàn toàn" not in out
