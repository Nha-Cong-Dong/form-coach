"""Kiểm tra nhãn bằng mắt trên một mẫu rep, có che (blind). CHỈ ĐỂ ƯỚC LƯỢNG ĐỘ NHIỄU NHÃN.

Vì sao che: nếu bạn chỉ xem các rep luật báo nhầm, bạn biết trước chúng "có vấn đề" nên dễ thấy
lỗi ở đó. Ở đây mẫu trộn bốn loại rep, và danh sách in ra không nói rep nào thuộc loại nào:
- báo nhầm (FP): luật báo lỗi, nhãn ghi không lỗi,
- đối chứng (TN): luật không báo, nhãn ghi không lỗi,
- báo đúng (TP): luật báo, nhãn ghi có lỗi,
- bỏ sót (FN): luật không báo, nhãn ghi có lỗi.

Cách dùng (từ gốc repo), với một lỗi, ví dụ shallow:
    python -m evaluation.audit_sample --error shallow
        → in danh sách xáo trộn; lưu đáp án ẩn vào outputs/audit_shallow.json
    (xem từng rep trên màn gán nhãn, KHÔNG đọc số đo, trả lời có lỗi / không / không chắc)
    python -m evaluation.audit_sample --error shallow --answers ynuyn...
        → y = có lỗi, n = không, u = không chắc; mỗi ký tự một rep theo thứ tự danh sách

Không sửa nhãn đã chốt dựa trên kết quả này: nó chỉ cho biết nhãn nhiễu cỡ nào (đưa vào hạn chế).
"""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from evaluation.error_analysis import outcomes
from evaluation.split import evaluation_rows
from formcoach.dataset import RepRow, build_dataset
from formcoach.exercises import get_exercise

CATEGORIES = {
    "fp": "báo nhầm (luật báo, nhãn ghi không)",
    "tn": "đối chứng (luật không báo, nhãn ghi không)",
    "tp": "báo đúng (luật báo, nhãn ghi có)",
    "fn": "bỏ sót (luật không báo, nhãn ghi có)",
}
DEFAULT_COUNTS = {"fp": 6, "tn": 3, "tp": 3, "fn": 3}
VALID_ANSWERS = "ynu"


@dataclass(frozen=True)
class SampleItem:
    position: int  # thứ tự trong danh sách in ra (từ 1)
    session_id: str
    rep_index: int  # chỉ số từ 0; màn gán nhãn đánh số từ 1
    category: str  # fp / tn / tp / fn: KHÔNG in ra khi tạo mẫu


def build_sample(
    rows: Sequence[RepRow],
    error: str,
    rule,
    counts: dict[str, int] | None = None,
    seed: int = 0,
) -> list[SampleItem]:
    """Lấy ngẫu nhiên (cố định theo seed) mỗi loại vài rep rồi xáo trộn chung."""
    counts = counts or DEFAULT_COUNTS
    rng = random.Random(seed)
    out = outcomes(rows, error, rule)
    picked: list[tuple[str, int]] = []
    for category, wanted in counts.items():
        pool = sorted(out[category], key=lambda i: (rows[i].session_id, rows[i].rep_index))
        picked += [(category, i) for i in rng.sample(pool, min(wanted, len(pool)))]
    rng.shuffle(picked)
    return [
        SampleItem(pos, rows[i].session_id, rows[i].rep_index, category)
        for pos, (category, i) in enumerate(picked, start=1)
    ]


def score(items: Sequence[SampleItem], answers: str) -> dict[str, dict[str, int]]:
    """Với mỗi loại: có bao nhiêu rep được trả lời y / n / u."""
    answers = answers.strip().lower()
    if len(answers) != len(items):
        raise ValueError(f"cần {len(items)} câu trả lời (y/n/u), đang có {len(answers)}")
    if set(answers) - set(VALID_ANSWERS):
        raise ValueError("câu trả lời chỉ gồm y (có lỗi), n (không), u (không chắc)")
    result = {c: {"y": 0, "n": 0, "u": 0} for c in CATEGORIES}
    for item, answer in zip(items, answers, strict=True):
        result[item.category][answer] += 1
    return result


def format_result(error: str, result: dict[str, dict[str, int]]) -> str:
    lines = [f"Kết quả xem bằng mắt cho {error}: (số rep trông có lỗi / không / không chắc)\n"]
    for category, label in CATEGORIES.items():
        r = result[category]
        total = sum(r.values())
        if total:
            lines.append(f"  {label}: {total} rep → có lỗi {r['y']}, không {r['n']}, ?{r['u']}")
    fp, tn = result["fp"], result["tn"]
    sure_fp, sure_tn = fp["y"] + fp["n"], tn["y"] + tn["n"]
    if sure_fp:
        lines.append(
            f"\n  Trong rep luật báo nhầm, {fp['y']}/{sure_fp} trông có lỗi thật "
            "→ nhãn thiếu lỗi (không phải luật báo sai)."
        )
    if sure_tn:
        lines.append(
            f"  Trong rep đối chứng (không ai báo), {tn['y']}/{sure_tn} trông có lỗi: "
            "mức nền của nhãn thiếu lỗi."
        )
    lines.append(
        "  Nếu 'báo nhầm' trông có lỗi nhiều hơn hẳn 'đối chứng' thì luật đang bắt được lỗi "
        "mà nhãn bỏ sót.\n  Mẫu nhỏ: chỉ là ước lượng thô, đừng sửa nhãn đã chốt vì nó."
    )
    return "\n".join(lines)


def key_path(out_dir: Path, error: str) -> Path:
    return out_dir / f"audit_{error}.json"


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.audit_sample")
    p.add_argument("--error", required=True, help="lỗi cần kiểm tra, vd shallow, hip_sag")
    p.add_argument("--answers", help="chuỗi y/n/u, một ký tự mỗi rep theo thứ tự danh sách")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--out", type=Path, default=Path("outputs"), help="nơi lưu đáp án ẩn")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--force", action="store_true", help="tạo lại mẫu dù đã có")
    args = p.parse_args(argv)

    path = key_path(args.out, args.error)
    if args.answers is not None:
        if not path.exists():
            raise SystemExit(f"chưa có mẫu {path}: chạy không kèm --answers trước")
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = [SampleItem(**r) for r in raw]
        print(format_result(args.error, score(items, args.answers)))
        return

    if path.exists() and not args.force:
        raise SystemExit(f"đã có mẫu {path} (danh sách cũ vẫn dùng được); --force để tạo lại")
    rule = get_exercise(args.exercise).error_rules().get(args.error)
    if rule is None:
        raise SystemExit(f"{args.error}: chưa có luật, không lấy mẫu được")
    rows = evaluation_rows(build_dataset(args.data, args.exercise))  # bỏ hiệp quay thử
    items = build_sample(rows, args.error, rule, seed=args.seed)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([vars(i) for i in items], ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"Mẫu {len(items)} rep cho lỗi {args.error}. Với mỗi rep, nhìn người que và trả lời:")
    print(f"'rep này có lỗi {args.error} không?' (y / n / u). Đừng đọc số đo trên màn hình.\n")
    for item in items:
        print(f"  {item.position:>2}.  {item.session_id}   rep {item.rep_index + 1}")
    print(
        f"\nXong thì chạy: python -m evaluation.audit_sample --error {args.error} --answers <chuỗi>"
    )
    print(f"(chuỗi gồm {len(items)} ký tự y/n/u theo thứ tự trên; đáp án ẩn nằm ở {path})")


if __name__ == "__main__":
    main()
