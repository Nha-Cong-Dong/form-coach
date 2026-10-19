from pathlib import Path

import pytest

from formcoach.video.reader import iter_frames, video_info


def test_video_info(make_video) -> None:
    info = video_info(make_video())
    assert info.fps == pytest.approx(24.0)
    assert (info.width, info.height) == (64, 48)


def test_iter_frames_reads_every_frame(make_video) -> None:
    frames = list(iter_frames(make_video(n_frames=12)))
    assert len(frames) == 12
    assert frames[0].shape == (48, 64, 3)  # (H, W, 3)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        video_info(tmp_path / "khong_co.mp4")
