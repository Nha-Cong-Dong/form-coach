"""Ghép các bước: nguồn keypoint → PoseSequence → tín hiệu → rep.

Một chỗ duy nhất gọi chuỗi FeatureExtractor → RepSegmenter, để CLI (`python -m formcoach`)
và sau này backend dùng chung, không mỗi nơi tự ghép một kiểu.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from formcoach.exercises import get_exercise
from formcoach.exercises.base import Exercise
from formcoach.features.extractor import FeatureExtractor
from formcoach.features.segmenter import RepSegmenter
from formcoach.models.base import FormClassifier
from formcoach.pose.session_json import SessionMeta, load_session_json
from formcoach.types import FeatureSeries, PoseSequence, Rep, Session

DEFAULT_MODEL = Path("assets/pose_landmarker_full.task")


def analyze(pose: PoseSequence, exercise: Exercise) -> tuple[FeatureSeries, list[Rep]]:
    """Khung xương của một hiệp → tín hiệu đã làm sạch + danh sách rep."""
    features = FeatureExtractor().extract(pose, exercise)
    return features, RepSegmenter().segment(features, exercise)


def classify_session(
    pose: PoseSequence, exercise: Exercise, classifier: FormClassifier, session_id: str
) -> Session:
    """Một hiệp → các rep kèm tập lỗi dự đoán (bộ phân loại đã fit, hoặc luật)."""
    _, reps = analyze(pose, exercise)
    return Session(session_id, exercise.name, classifier.predict(reps))


@dataclass(frozen=True)
class Source:
    """Một hiệp đã nạp, từ file JSON (trang quay) hoặc video (thử nghiệm offline)."""

    pose: PoseSequence
    exercise: Exercise
    times_s: np.ndarray  # (T,) thời điểm từng khung, tính từ khung đầu
    meta: SessionMeta | None  # chỉ có với file JSON


def load_source(path: Path, model_path: Path = DEFAULT_MODEL) -> Source:
    """Đọc .json (trang quay) hoặc video (chạy MediaPipe Python). Video mặc định là push-up."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        pose, meta = load_session_json(path)
        times = (meta.timestamps_ms - meta.timestamps_ms[0]) / 1000.0
        return Source(pose, get_exercise(meta.exercise), times, meta)

    # Import trễ: chỉ đường video mới cần MediaPipe/OpenCV.
    from formcoach.pose.mediapipe_estimator import MediaPipeEstimator

    pose = MediaPipeEstimator(model_path).estimate(path)
    times = np.arange(len(pose.keypoints)) / pose.fps
    return Source(pose, get_exercise("pushup"), times, None)


@dataclass(frozen=True)
class FrameTiming:
    """Độ đều của khoảng cách giữa các khung (ms). Dùng để quyết định có cần lấy mẫu lại."""

    median_ms: float
    std_ms: float
    p95_ms: float
    max_ms: float
    long_gaps: int  # số khoảng cách > 3 × trung vị (trình duyệt khựng, mất khung)

    @property
    def jitter_ratio(self) -> float:
        """Độ lệch chuẩn / trung vị: 0 = đều tuyệt đối."""
        return self.std_ms / self.median_ms


def frame_timing(timestamps_ms: np.ndarray) -> FrameTiming:
    steps = np.diff(np.asarray(timestamps_ms, dtype=float))
    median = float(np.median(steps))
    return FrameTiming(
        median_ms=median,
        std_ms=float(np.std(steps)),
        p95_ms=float(np.percentile(steps, 95)),
        max_ms=float(steps.max()),
        long_gaps=int((steps > 3 * median).sum()),
    )
