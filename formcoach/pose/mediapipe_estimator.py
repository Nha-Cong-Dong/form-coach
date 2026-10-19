"""PoseEstimator dùng MediaPipe Python (Tasks API) cho đường thử nghiệm offline.

Không dùng để tạo dữ liệu train: dữ liệu train lấy từ MediaPipe JS ở trang quay.
File này import mediapipe/cv2 nên không được export trong `formcoach/pose/__init__.py`,
để phần còn lại của `formcoach` import được mà không cần tải MediaPipe.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from formcoach.pose.base import PoseEstimator
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.types import PoseSequence
from formcoach.video.reader import iter_frames, video_info


class MediaPipeEstimator(PoseEstimator):
    """Chạy PoseLandmarker ở chế độ VIDEO trên mọi khung của một video."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Chưa có model: {self.model_path}. Xem lệnh tải trong tools/probe_mediapipe.py."
            )

    def estimate(self, video_path: Path) -> PoseSequence:
        """Trả PoseSequence (T, 33, 3) gồm x, y, visibility; khung không có người là NaN.

        T là số khung đọc được thật (không tin frame_count trong metadata).
        frame_size lấy từ khung đọc được, tức sau khi OpenCV đã xoay theo metadata.
        """
        fps = video_info(video_path).fps
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        rows: list[np.ndarray] = []
        frame_size: tuple[int, int] | None = None
        last_ts = -1
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            for i, frame_bgr in enumerate(iter_frames(video_path)):
                if frame_size is None:
                    h, w = frame_bgr.shape[:2]
                    frame_size = (w, h)
                # VIDEO mode bắt buộc timestamp (ms) tăng ngặt; làm tròn có thể trùng nên ép +1.
                ts = max(int(round(i * 1000 / fps)), last_ts + 1)
                last_ts = ts
                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts
                )
                if result.pose_landmarks:
                    lms = result.pose_landmarks[0]
                    rows.append(np.array([[lm.x, lm.y, lm.visibility] for lm in lms]))
                else:
                    rows.append(np.full((len(MEDIAPIPE_JOINTS), 3), np.nan))

        if frame_size is None:
            raise ValueError(f"Video không có khung nào đọc được: {video_path}")
        return PoseSequence(
            keypoints=np.stack(rows),
            joint_names=list(MEDIAPIPE_JOINTS),
            fps=fps,
            frame_size=frame_size,
        )
