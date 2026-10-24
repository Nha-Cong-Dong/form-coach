"""Độ nhất quán của chính người gán nhãn: gán lại MÙ một mẫu rep, so với nhãn đã chốt (v3).

Cho biết "trần" của mọi mô hình học từ nhãn: nếu chính người gán chỉ tự khớp ở mức nào đó với
mình, mô hình không thể (và không nên) khớp với nhãn cao hơn nhiều. Khác `audit_sample` (lấy mẫu
lệch quanh luật, từng lỗi một): ở đây lấy NGẪU NHIÊN ĐƠN GIẢN để tỉ lệ có lỗi giống bộ nhãn thật
(kappa phụ thuộc tỉ lệ đó), và gán lại toàn bộ tập lỗi của mỗi rep.

Cách dùng (từ gốc repo):
    python -m evaluation.relabel_consistency sample
        → lưu đáp án ẩn vào outputs/relabel_pushup.json, in đường link màn kiểm tra (#audit/...)
    (mở link trên web đang chạy, gán mù 30 rep; màn không hiện nhãn cũ, hiệp, số đo)
    python -m evaluation.relabel_consistency score --answers "0,13,x,2,..."
        → tỉ lệ khớp, Cohen's kappa (kèm khoảng tin cậy bootstrap) từng lỗi, khớp toàn bộ tập lỗi

Không sửa nhãn đã chốt dựa trên kết quả này: nó chỉ đo độ nhiễu nhãn (đưa vào hạn chế).
"""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.baseline import MAIN_ERRORS
from evaluation.split import evaluation_rows
from formcoach.dataset import RepRow, build_dataset

DEFAULT_N = 30
DEFAULT_SEED = 0
N_BOOTSTRAP = 1000


@dataclass(frozen=True)
class Item:
    """Một rep trong mẫu, theo thứ tự hiện ra trên màn kiểm tra (đã xáo trộn)."""

    session_id: str
    rep_index: int
    errors: frozenset[str]  # nhãn đã chốt (lần 1); KHÔNG in ra khi tạo mẫu


def draw_sample(rows: Sequence[RepRow], n: int, seed: int) -> list[RepRow]:
    """Lấy ngẫu nhiên đơn giản n rep (không lặp), thứ tự đã xáo trộn; cố định theo seed."""
    if n > len(rows):
        raise ValueError(f"chỉ có {len(rows)} rep, không lấy được mẫu {n}")
    return random.Random(seed).sample(list(rows), n)


def audit_hash(items: Sequence[Item]) -> str:
    """Đoạn sau dấu # của màn kiểm tra: `audit/<hiệp>~<rep>,...` (không chứa nhãn)."""
    return "audit/" + ",".join(f"{it.session_id}~{it.rep_index}" for it in items)


Answer = frozenset[str] | None  # None = người gán nói "không phải rep"


def parse_answers(text: str, n: int, error_labels: Sequence[str]) -> list[Answer]:
    """Chuỗi đáp án từ màn kiểm tra: mỗi rep một mục, cách nhau dấu phẩy.

    "0" = không lỗi; "x" = không phải rep; chữ số 1–9 = lỗi thứ k trong `error_labels` (vd "13").
    """
    tokens = [t.strip() for t in text.split(",")]
    if len(tokens) != n:
        raise ValueError(f"cần {n} đáp án, nhận {len(tokens)}")
    answers: list[Answer] = []
    for pos, tok in enumerate(tokens, start=1):
        if tok.lower() == "x":
            answers.append(None)
            continue
        if tok == "0":
            answers.append(frozenset())
            continue
        if not tok.isdigit():
            raise ValueError(f"đáp án {pos}: {tok!r} không hợp lệ (dùng 0, x hoặc chữ số lỗi)")
        errors = set()
        for ch in tok:
            k = int(ch)
            if not 1 <= k <= len(error_labels):
                raise ValueError(f"đáp án {pos}: không có lỗi số {k}")
            errors.add(error_labels[k - 1])
        answers.append(frozenset(errors))
    return answers


def cohen_kappa(a: Sequence[bool], b: Sequence[bool]) -> float | None:
    """Mức khớp vượt trên mức tình cờ giữa hai lần gán có/không. None khi không xác định.

    kappa = (p_o − p_e) / (1 − p_e); p_o = tỉ lệ khớp, p_e = tỉ lệ khớp nếu hai lần gán độc lập
    với cùng tỉ lệ "có" như thật. Không xác định khi p_e = 1 (cả hai lần đều toàn "có" hoặc toàn
    "không": không có gì để phân biệt).
    """
    n = len(a)
    if n == 0 or n != len(b):
        return None
    p_o = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    p_e = pa * pb + (1 - pa) * (1 - pb)
    if p_e >= 1:
        return None
    return (p_o - p_e) / (1 - p_e)


def bootstrap_kappa(
    a: Sequence[bool], b: Sequence[bool], seed: int = 0, n_boot: int = N_BOOTSTRAP
) -> tuple[float, float] | None:
    """Khoảng tin cậy 95% của kappa, lấy mẫu lại theo rep (cặp a[i], b[i] đi cùng nhau).

    Mẫu lại có kappa không xác định thì bỏ; còn dưới một nửa xác định thì trả None.
    """
    rng = random.Random(seed)
    n = len(a)
    values = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        k = cohen_kappa([a[i] for i in idx], [b[i] for i in idx])
        if k is not None:
            values.append(k)
    if len(values) < n_boot / 2:
        return None
    values.sort()
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]


def score(
    items: Sequence[Item],
    answers: Sequence[Answer],
    error_labels: Sequence[str],
    main_errors: Sequence[str],
    seed: int = 0,
) -> dict[str, Any]:
    """So lần 1 (nhãn đã chốt) với lần 2 (gán lại mù). Rep lần 2 nói "không phải rep" bị bỏ
    khỏi mọi chỉ số (lần 1 coi là rep hợp lệ) và được đếm riêng."""
    pairs = [(it.errors, ans) for it, ans in zip(items, answers, strict=True) if ans is not None]
    per_error = {}
    for e in error_labels:
        first = [e in f for f, _ in pairs]
        second = [e in s for _, s in pairs]
        n = len(pairs)
        per_error[e] = {
            "n": n,
            "pos_first": sum(first),
            "pos_second": sum(second),
            "agreement": sum(x == y for x, y in zip(first, second, strict=True)) / n if n else None,
            "kappa": cohen_kappa(first, second),
            "kappa_ci": bootstrap_kappa(first, second, seed=seed) if n else None,
        }
    main = set(main_errors)
    return {
        "n_items": len(items),
        "n_not_rep": len(items) - len(pairs),
        "exact_all": sum(f == s for f, s in pairs) / len(pairs) if pairs else None,
        "exact_main": sum(f & main == s & main for f, s in pairs) / len(pairs) if pairs else None,
        "per_error": per_error,
    }


def report(result: dict[str, Any], main_errors: Sequence[str]) -> str:
    def f(v: float | None) -> str:
        return "—" if v is None else f"{v:.2f}".replace(".", ",")

    lines = [
        f"{result['n_items']} rep, {result['n_not_rep']} rep lần 2 nói 'không phải rep' (bỏ qua).",
        f"{'lỗi':<22}{'có (lần 1/2)':>14}{'khớp':>8}{'kappa':>8}  KTC 95%",
    ]
    for e, r in result["per_error"].items():
        ci = r["kappa_ci"]
        ci_text = "—" if ci is None else f"[{f(ci[0])}, {f(ci[1])}]"
        tag = "" if e in main_errors else " (thử nghiệm)"
        lines.append(
            f"{e + tag:<22}{r['pos_first']:>7}/{r['pos_second']:<6}"
            f"{f(r['agreement']):>8}{f(r['kappa']):>8}  {ci_text}"
        )
    lines += [
        f"Khớp toàn bộ tập lỗi (4 lỗi chính): {f(result['exact_main'])}"
        f" · (cả 5 lỗi): {f(result['exact_all'])}",
        "Mốc kappa hay dùng: < 0,4 yếu · 0,4–0,6 vừa · 0,6–0,8 khá · > 0,8 tốt.",
        "Mẫu nhỏ: khoảng tin cậy rộng. Gán lại khi còn nhớ nhãn cũ (vd sau 1 ngày) thì số này"
        " lạc quan hơn độ nhất quán thật.",
    ]
    return "\n".join(lines)


def key_path(out_dir: Path, exercise: str) -> Path:
    return out_dir / f"relabel_{exercise}.json"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # link: in lại đường link màn kiểm tra của mẫu đã có (không in nhãn), khi lỡ mất dòng in cũ.
    parser.add_argument("command", choices=["sample", "link", "score"])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--exercise", default="pushup")
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--answers", help="chuỗi đáp án từ màn kiểm tra (lệnh score)")
    parser.add_argument("--force", action="store_true", help="ghi đè mẫu đã có (lệnh sample)")
    args = parser.parse_args(argv)
    path = key_path(args.out, args.exercise)

    if args.command == "sample":
        if path.exists() and not args.force:
            # Không lấy mẫu mới sau khi đã gán: chọn lại mẫu "dễ" sẽ làm số đẹp giả.
            parser.error(f"{path} đã có; dùng lại mẫu đó (hoặc --force nếu chắc chắn)")
        ds = build_dataset(args.data, args.exercise)
        rows = draw_sample(evaluation_rows(ds), args.n, args.seed)
        items = [Item(r.session_id, r.rep_index, r.errors) for r in rows]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "exercise": args.exercise,
                    "seed": args.seed,
                    "error_labels": list(ds.error_labels),
                    "items": [
                        {
                            "session_id": i.session_id,
                            "rep_index": i.rep_index,
                            "errors": sorted(i.errors),
                        }
                        for i in items
                    ],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"Đã lấy {len(items)} rep ngẫu nhiên (seed {args.seed}); đáp án ẩn ở {path}.")
        print("Đừng mở file đó trước khi gán xong. Mở trên web đang chạy (đã đăng nhập):")
        print(f"  https://localhost:5173/#{audit_hash(items)}")
        return

    if not path.exists():
        parser.error(f"chưa có mẫu {path}; chạy lệnh sample trước")
    key = json.loads(path.read_text(encoding="utf-8"))
    items = [Item(i["session_id"], i["rep_index"], frozenset(i["errors"])) for i in key["items"]]
    if args.command == "link":
        print(f"Mẫu {len(items)} rep tạo lúc {key['created_at']}. Mở trên web đang chạy:")
        print(f"  https://localhost:5173/#{audit_hash(items)}")
        return

    if not args.answers:
        parser.error("lệnh score cần --answers")
    answers = parse_answers(args.answers, len(items), key["error_labels"])
    main_errors = MAIN_ERRORS[args.exercise]
    result = score(items, answers, key["error_labels"], main_errors, seed=key["seed"])
    out = path.with_name(f"relabel_{args.exercise}_result.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report(result, main_errors))
    print(f"\nĐã lưu {out}.")


if __name__ == "__main__":
    main()
