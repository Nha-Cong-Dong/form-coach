"""Thử nhanh MediaPipe Pose trên một clip push-up (bước 1, cổng rủi ro).

Mục đích: trước khi viết pipeline, xem pose có dùng được cho push-up không.
Script in thông tin video, tỉ lệ khung có người, visibility từng khớp theo hai bên,
và lưu 3 ảnh có vẽ khung xương (đầu / giữa / đáy rep) để nhìn bằng mắt.

Đây là công cụ thử nghiệm, không phải pipeline: chạy MediaPipe **Python**, còn dữ liệu
train sẽ lấy từ MediaPipe **JS** (xem ARCHITECTURE). Kết luận cuối cùng về pose chỉ chắc
sau bước 9b(i).

Chuẩn bị model (một lần):
    mkdir -p assets
    curl -L -o assets/pose_landmarker_full.task \\
      https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task

Chạy từ gốc repo, dạng module (cùng quy ước với các công cụ khác trong tools/):
    python -m tools.probe_mediapipe data/videos/pushup.mp4
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

# Index theo enum vision.PoseLandmark (đã kiểm tra với mediapipe 1.1.1).
JOINTS = {
    "shoulder": (11, 12),
    "elbow": (13, 14),
    "wrist": (15, 16),
    "hip": (23, 24),
    "ankle": (27, 28),
}
SIDES = ("left", "right")


def video_info(cap: cv2.VideoCapture) -> dict[str, float]:
    """Thông tin OpenCV khai báo trong metadata (chưa chắc đúng với số khung đọc được)."""
    return {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": cap.get(cv2.CAP_PROP_FRAME_COUNT),
        "width": cap.get(cv2.CAP_PROP_FRAME_WIDTH),
        "height": cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
        "orientation_meta": cap.get(cv2.CAP_PROP_ORIENTATION_META),
        "orientation_auto": cap.get(cv2.CAP_PROP_ORIENTATION_AUTO),
    }


def run_pose(video_path: Path, model_path: Path) -> tuple[np.ndarray, list[np.ndarray], float]:
    """Chạy PoseLandmarker (VIDEO mode) trên mọi khung.

    Trả về:
        kp: (T, 33, 4) gồm x, y, visibility, presence; khung không có người là NaN.
        frames: các khung BGR đã đọc (clip ngắn nên giữ trong RAM được).
        fps: fps khai báo, dùng để tính timestamp.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Không mở được video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    rows: list[np.ndarray] = []
    frames: list[np.ndarray] = []
    last_ts = -1
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        i = 0
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            # VIDEO mode bắt buộc timestamp (ms) tăng ngặt; làm tròn có thể trùng nên ép +1.
            ts = max(int(round(i * 1000 / fps)), last_ts + 1)
            last_ts = ts
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)  # OpenCV đọc BGR, MediaPipe cần RGB
            result = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts
            )
            if result.pose_landmarks:
                lms = result.pose_landmarks[0]
                rows.append(np.array([[lm.x, lm.y, lm.visibility, lm.presence] for lm in lms]))
            else:
                rows.append(np.full((33, 4), np.nan))
            frames.append(frame_bgr)
            i += 1
    cap.release()
    return np.stack(rows) if rows else np.empty((0, 33, 4)), frames, fps


def elbow_angle_px(kp: np.ndarray, side: int, size: tuple[int, int]) -> np.ndarray:
    """Góc khuỷu (độ) theo pixel, chỉ để chọn khung 'đáy rep'. Bước 3 sẽ viết bản chuẩn có test."""
    w, h = size
    scale = np.array([w, h])
    s, e, wr = (kp[:, JOINTS[j][side], :2] * scale for j in ("shoulder", "elbow", "wrist"))
    v1, v2 = s - e, wr - e
    cos = np.sum(v1 * v2, axis=1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1))
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def draw(frame: np.ndarray, kp_frame: np.ndarray, connections: list, label: str) -> np.ndarray:
    """Vẽ khung xương: bên trái màu cam, bên phải màu xanh, khớp mờ (visibility < 0,5) màu xám."""
    img = frame.copy()
    h, w = img.shape[:2]
    if np.isnan(kp_frame).all():
        cv2.putText(img, f"{label}: KHONG THAY NGUOI", (20, 40), 0, 1.0, (0, 0, 255), 2)
        return img
    pts = [(int(x * w), int(y * h)) for x, y in kp_frame[:, :2]]
    for c in connections:
        cv2.line(img, pts[c.start], pts[c.end], (220, 220, 220), 2)
    for idx, (x, y) in enumerate(pts):
        vis = kp_frame[idx, 2]
        if vis < 0.5:
            color = (128, 128, 128)
        elif idx % 2 == 1:  # index lẻ là bên trái (11 = left_shoulder, 13 = left_elbow...)
            color = (0, 140, 255)
        else:
            color = (255, 160, 0)
        cv2.circle(img, (x, y), 5, color, -1)
    cv2.putText(img, label, (20, 40), 0, 1.0, (0, 255, 0), 2)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video", type=Path)
    parser.add_argument("--model", type=Path, default=Path("assets/pose_landmarker_full.task"))
    parser.add_argument("--out", type=Path, default=Path("outputs/probe"))
    args = parser.parse_args()
    if not args.model.exists():
        raise SystemExit(f"Chưa có model: {args.model}. Xem lệnh tải trong docstring của file này.")

    cap = cv2.VideoCapture(str(args.video))
    info = video_info(cap)
    cap.release()

    t0 = time.perf_counter()
    kp, frames, fps = run_pose(args.video, args.model)
    elapsed = time.perf_counter() - t0
    if not frames:
        raise SystemExit("Không đọc được khung nào.")

    h, w = frames[0].shape[:2]
    detected = ~np.isnan(kp[:, 0, 0])

    print(f"== {args.video.name}  (mediapipe {mp.__version__}, opencv {cv2.__version__})")
    print(
        f"Metadata : {info['width']:.0f}x{info['height']:.0f}, {info['fps']:.2f} fps, "
        f"{info['frame_count']:.0f} khung, orientation_meta={info['orientation_meta']:.0f}, "
        f"auto_rotate={info['orientation_auto']:.0f}"
    )
    print(f"Đọc thật : {w}x{h}, {len(frames)} khung ({len(frames) / fps:.1f} s)")
    if (w, h) != (int(info["width"]), int(info["height"])):
        print("  ! Kích thước khung đọc được khác metadata: video có thể đã bị xoay.")
    if h > w:
        print("  ! Khung đang DỌC. Push-up nên quay NGANG để thấy hết thân.")
    print(f"Thời gian chạy pose: {elapsed:.1f} s ({len(frames) / elapsed:.1f} khung/s)")
    print(f"Khung có người: {detected.sum()}/{len(frames)} ({100 * detected.mean():.0f}%)")

    if detected.any():
        print("\nVisibility trên các khung có người (trung bình / nhỏ nhất):")
        print(f"  {'khớp':<9} {'trái':>13} {'phải':>13}")
        for name, (li, ri) in JOINTS.items():
            cells = []
            for idx in (li, ri):
                v = kp[detected, idx, 2]
                cells.append(f"{v.mean():.2f} / {v.min():.2f}")
            print(f"  {name:<9} {cells[0]:>13} {cells[1]:>13}")

        side_vis = [
            np.nanmean(kp[detected][:, [JOINTS[j][s] for j in JOINTS], 2]) for s in range(2)
        ]
        best = int(np.argmax(side_vis))
        print(
            f"\nBên nhìn rõ hơn: {SIDES[best]} (visibility TB {side_vis[best]:.2f} "
            f"so với {side_vis[1 - best]:.2f})"
        )
        angle = elbow_angle_px(kp[:, :, :3], best, (w, h))
        # Chỉ tin góc ở khung mà cả vai, khuỷu, cổ tay của bên này đều nhìn rõ.
        arm = [JOINTS[j][best] for j in ("shoulder", "elbow", "wrist")]
        valid = detected & (np.nan_to_num(kp[:, arm, 2]) >= 0.5).all(axis=1)
        good = angle[valid]
        print(
            f"Góc khuỷu bên {SIDES[best]} (sơ bộ, chưa làm mượt): "
            f"{valid.sum()}/{len(frames)} khung có tay nhìn rõ"
        )
        if good.size:
            p5, p50, p95 = np.percentile(good, [5, 50, 95])
            print(f"  phân vị 5% / 50% / 95%: {p5:.0f}° / {p50:.0f}° / {p95:.0f}°")
            print(
                f"  khung có góc < 30° (gần như chắc là khung lỗi): "
                f"{(good < 30).sum()} trong số khung tay nhìn rõ, "
                f"{(angle[detected] < 30).sum()} trong số mọi khung có người"
            )
        det_idx = np.flatnonzero(detected)
        picks = {"dau": det_idx[0], "giua": det_idx[len(det_idx) // 2]}
        if good.size:
            # Khung "đáy": góc gần phân vị 5% nhất, tránh vài khung lỗi có góc gần 0°.
            valid_idx = np.flatnonzero(valid)
            picks["day"] = int(valid_idx[np.argmin(np.abs(good - p5))])
    else:
        picks = {"dau": 0, "giua": len(frames) // 2}

    args.out.mkdir(parents=True, exist_ok=True)
    connections = vision.PoseLandmarksConnections.POSE_LANDMARKS
    print("\nẢnh đã lưu:")
    for tag, i in picks.items():
        label = f"{tag} - khung {i} ({i / fps:.1f}s)"
        path = args.out / f"{args.video.stem}_{tag}.png"
        cv2.imwrite(str(path), draw(frames[i], kp[i], connections, label))
        print(f"  {path}")


if __name__ == "__main__":
    main()
