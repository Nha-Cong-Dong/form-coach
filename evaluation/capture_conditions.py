"""Thí nghiệm điều kiện quay: áo và góc đặt máy làm hệ thống báo nhầm bao nhiêu khi TẬP ĐÚNG FORM.

Mọi hiệp thí nghiệm đều cố ý tập đúng, nên đáp án biết trước là "không lỗi": không cần gán
nhãn, rep nào bị báo lỗi là báo nhầm. Đo độ bền khi điều kiện đổi (domain shift), không đánh
giá mô hình, nên không chia train/test. Hiệp thí nghiệm chưa gán nhãn nên không nằm trong dữ
liệu huấn luyện bộ phân loại (không rò rỉ). ĐỪNG gán nhãn các hiệp này.

Quay bằng màn Quay dữ liệu, không chọn lỗi cố ý, ô ghi chú theo mẫu (thứ tự tuỳ ý):
    ao:khong goc:0 rep:10      (cởi trần, máy ngang hông, tập 10 rep)
    ao:co goc:20 rep:10        (mặc áo, máy lệch ~20°)

Chạy (từ gốc repo):
    python -m evaluation.capture_conditions [--model rf]
In theo từng điều kiện: tỉ lệ báo nhầm từng lỗi (luật và mô hình), tỉ lệ rep bị báo ít nhất một
lỗi, độ lệch đặc trưng so với điều kiện chuẩn (cởi trần, 0°), độ tách vai, rep đếm được.
Mỗi điều kiện chỉ vài hiệp, rep cùng hiệp giống nhau: đọc là xu hướng, không phải số chính xác.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from formcoach.conditions import Condition, parse_condition
from formcoach.dataset import build_dataset
from formcoach.exercises import get_exercise
from formcoach.features.view import shoulder_separation
from formcoach.models.base import FormClassifier
from formcoach.models.registry import make_classifier
from formcoach.models.train import train_classifier
from formcoach.pipeline import analyze
from formcoach.pose.session_json import SessionFormatError, load_session_json

# Đặc trưng in độ lệch: góc khuỷu (shallow, incomplete_lockout) và độ lệch hông (hip_sag/high).
FEATURES = ("min_elbow_angle", "top_elbow_angle", "min_hip_offset", "median_hip_offset")
BASELINE = (False, 0)  # cởi trần, máy ngang hông


def label_of(key: tuple[bool, int]) -> str:
    shirt, angle = key
    return f"{'mặc áo' if shirt else 'cởi trần'}, {angle}°"


@dataclass
class SessionResult:
    session_id: str
    condition: Condition
    n_reps: int
    flagged: dict[str, dict[str, int]]  # mô hình -> lỗi -> số rep bị báo
    any_flagged: dict[str, int]  # mô hình -> số rep bị báo ít nhất một lỗi
    features: dict[str, list[float]]  # đặc trưng -> giá trị từng rep
    separation: float


def run_session(
    path: Path, classifiers: dict[str, FormClassifier], error_labels: Sequence[str]
) -> SessionResult | None:
    """Một hiệp có ghi chú điều kiện → số rep bị báo lỗi theo từng mô hình. Không phải hiệp
    thí nghiệm (không có mẫu ghi chú, hoặc có lỗi cố ý) → None."""
    pose, meta = load_session_json(path)
    cond = parse_condition(meta.notes)
    if cond is None or meta.set_errors:
        return None
    _, reps = analyze(pose, get_exercise(meta.exercise))
    flagged, any_flagged = {}, {}
    for name, clf in classifiers.items():
        preds = clf.predict(reps)
        flagged[name] = {e: sum(e in p.errors for p in preds) for e in error_labels}
        any_flagged[name] = sum(bool(p.errors) for p in preds)
    feats = {f: [r.features.get(f, float("nan")) for r in reps] for f in FEATURES}
    return SessionResult(
        meta.session_id, cond, len(reps), flagged, any_flagged, feats, shoulder_separation(pose)
    )


def _median(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.median(arr)) if arr.size else float("nan")


def _fmt(v: float, digits: int = 2) -> str:
    return "—" if not np.isfinite(v) else f"{v:.{digits}f}".replace(".", ",")


def report(results: Sequence[SessionResult], error_labels: Sequence[str]) -> str:
    if not results:
        return "Chưa có hiệp thí nghiệm nào (ghi chú dạng 'ao:khong goc:0 rep:10', không lỗi cố ý)."
    models = list(results[0].flagged)
    groups: dict[tuple[bool, int], list[SessionResult]] = {}
    for r in results:
        groups.setdefault(r.condition.key, []).append(r)
    order = sorted(groups)
    base = groups.get(BASELINE)
    base_median = (
        {f: _median([v for r in base for v in r.features[f]]) for f in FEATURES} if base else None
    )

    lines = []
    for key in order:
        rs = groups[key]
        n = sum(r.n_reps for r in rs)
        lines.append(f"\n== {label_of(key)}: {len(rs)} hiệp, {n} rep")
        for m in models:
            anyk = sum(r.any_flagged[m] for r in rs)
            per_err = ", ".join(f"{e} {sum(r.flagged[m][e] for r in rs)}/{n}" for e in error_labels)
            rate = _fmt(anyk / n if n else float("nan"))
            lines.append(f"  [{m}] báo ≥1 lỗi: {anyk}/{n} ({rate}) · {per_err}")
            # Từng hiệp: rep cùng hiệp giống nhau, nên xem dao động giữa các hiệp.
            lines.append(
                "      từng hiệp: " + ", ".join(f"{r.any_flagged[m]}/{r.n_reps}" for r in rs)
            )
        feats = []
        for f in FEATURES:
            med = _median([v for r in rs for v in r.features[f]])
            delta = (
                f" (lệch {_fmt(med - base_median[f])})"
                if base_median and key != BASELINE and np.isfinite(base_median[f])
                else ""
            )
            feats.append(f"{f} {_fmt(med)}{delta}")
        lines.append("  đặc trưng (trung vị): " + " · ".join(feats))
        seps = [r.separation for r in rs]
        lines.append(f"  độ tách vai: {' / '.join(_fmt(s) for s in seps)}")
        counted = [
            f"{r.n_reps}/{r.condition.reps_done}" for r in rs if r.condition.reps_done is not None
        ]
        if counted:
            lines.append(f"  bộ đếm (đếm được/thật sự tập): {', '.join(counted)}")
    if base is None:
        lines.append(
            "\nChưa có điều kiện chuẩn (ao:khong goc:0): không tính được độ lệch đặc trưng."
        )
    lines.append(
        "\nĐáp án biết trước là 'không lỗi': mọi lỗi báo ra là báo nhầm. Ít hiệp mỗi điều kiện:"
        " đọc là xu hướng."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--exercise", default="pushup")
    parser.add_argument("--model", default="rf", help="mô hình so cùng luật (rf | stump)")
    args = parser.parse_args(argv)

    exercise = get_exercise(args.exercise)
    # Mô hình như trong app: học trên mọi rep đã gán nhãn. Hiệp thí nghiệm chưa gán nhãn nên
    # không có trong đó. Không học được (không có dữ liệu) → lùi luật, in rõ tên thật.
    model, model_name = train_classifier(
        args.model, exercise, build_dataset(args.data, args.exercise)
    )
    classifiers: dict[str, FormClassifier] = {"rules": make_classifier("rules", exercise)}
    if model_name != "rules":
        classifiers[model_name] = model

    results, skipped = [], []
    for path in sorted((args.data / "sessions" / args.exercise).glob("*.json")):
        try:
            r = run_session(path, classifiers, exercise.error_labels)
        except SessionFormatError as e:
            skipped.append(f"{path.stem}: {e}")
            continue
        if r is not None:
            results.append(r)
    for s in skipped:
        print(f"bỏ qua {s}")
    print(f"Mô hình: {', '.join(classifiers)}")
    print(report(results, exercise.error_labels))


if __name__ == "__main__":
    main()
