"""Chia train/test theo NHÓM buổi quay: kiểm định chéo bỏ ra một nhóm (leave-one-group-out).

Vì sao theo nhóm, không theo rep: các rep cùng buổi giống nhau ở chỗ đặt máy, độ mỏi, cách giữ
đầu hôm đó (góc cổ tập đúng của hai ngày quay thử lệch nhau 10–20°). Chia theo rep thì model được
"nhìn trước" đúng buổi nó bị chấm → điểm cao giả (rò rỉ dữ liệu).

Hai cách nhóm:
- "block" (kết quả chính, chốt 2026-10-21 trước khi có dữ liệu): hiệp cách hiệp trước ≥ BLOCK_GAP
  thì sang buổi mới. Điều kiện: mỗi buổi người quay đặt lại máy và ghi vào ghi chú buổi quay, nên
  hai buổi cùng ngày khác nhau về chỗ đặt máy, giờ (ánh sáng) và độ mỏi.
- "day": mọi hiệp cùng ngày luôn cùng một phía. Cách bảo thủ hơn, luôn báo kèm để so: nếu điểm
  theo "block" cao hơn hẳn "day" thì các buổi cùng ngày đang rò rỉ sang nhau.

Hiệp quay thử (dùng để chọn ngưỡng luật) KHÔNG BAO GIỜ vào tập chấm điểm.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from formcoach.dataset import Dataset, RepRow

# Hiệp quay thử: ngưỡng trong docs/labeling-criteria.md được chọn từ chính các hiệp này, chấm
# trên chúng là rò rỉ. Quay thử thêm (vd hip_sag võng rõ) thì thêm session_id vào đây.
PILOT_SESSIONS = frozenset(
    {
        "2026-10-19T23-38-38_pushup",
        "2026-10-20T10-14-01_pushup",
        "2026-10-20T10-14-51_pushup",
        "2026-10-20T10-15-32_pushup",
        "2026-10-20T10-16-09_pushup",
        "2026-10-20T10-16-48_pushup",
        "2026-10-20T10-17-26_pushup",
        "2026-10-20T11-31-16_pushup",  # hiệp thử ô ghi chú (bước 3d), không phải dữ liệu
        "2026-10-21T18-34-56_pushup",  # hip_sag quay thử võng rõ, để chọn ngưỡng hip_sag
    }
)
# Lưới an toàn: mọi hiệp quay trước mốc này đều là thử nghiệm (kể cả hiệp quên ghi vào danh sách
# trên). Dataset bắt đầu từ 20/10 18:00, sau buổi quay thử sáng 20/10 (buổi tối 20/10 bị lỡ nên
# thực tế dữ liệu đầu tiên là 21/10). Hiệp hip_sag quay thử cùng ngày với buổi dataset đầu tiên
# → ngưỡng hip_sag có thể rò rỉ nhẹ, ghi vào phần hạn chế.
DATASET_START = datetime(2026, 10, 20, 18, 0, tzinfo=timezone(timedelta(hours=7)))
BLOCK_GAP = timedelta(hours=1)
# "Ngày tập" đổi lúc 04:00 sáng, không phải nửa đêm: buổi bắt đầu 23:50 kéo sang 00:10 vẫn là
# một ngày (đã từng quay lúc 23:38). Cắt ở nửa đêm thì một buổi bị chia ra train và test.
DAY_STARTS_AT = timedelta(hours=4)

GroupMode = Literal["day", "block"]


def training_day(at: datetime) -> date:
    """Ngày tập của một thời điểm: trước 04:00 sáng vẫn tính là ngày hôm trước."""
    return (at - DAY_STARTS_AT).date()


def is_pilot(row: RepRow) -> bool:
    return row.session_id in PILOT_SESSIONS or row.recorded_at < DATASET_START


def evaluation_rows(dataset: Dataset) -> list[RepRow]:
    """Các rep dùng để chấm điểm: bỏ hiệp quay thử."""
    return [r for r in dataset.rows if not is_pilot(r)]


GROUP_NAMES = {"day": "ngày", "block": "buổi"}


def group_keys(rows: Sequence[RepRow], mode: GroupMode = "block") -> list[str]:
    """Nhóm của từng rep (cùng thứ tự với rows). Mọi rep của một hiệp luôn cùng nhóm."""
    if mode == "day":
        return [training_day(r.recorded_at).isoformat() for r in rows]
    if mode != "block":
        raise ValueError(f"cách nhóm không hỗ trợ: {mode!r}")

    starts = sorted({(r.recorded_at, r.session_id) for r in rows})
    block_of: dict[str, str] = {}
    prev = None
    k = 0
    for at, sid in starts:
        if prev is None or training_day(at) != training_day(prev):
            k = 1
        elif at - prev >= BLOCK_GAP:
            k += 1
        block_of[sid] = f"{training_day(at).isoformat()}#{k}"
        prev = at
    return [block_of[r.session_id] for r in rows]


@dataclass(frozen=True)
class Fold:
    """Một lần chia: nhóm `test_group` làm test, các nhóm còn lại làm train (chỉ số dòng)."""

    test_group: str
    train: tuple[int, ...]
    test: tuple[int, ...]


def leave_one_group_out(groups: Sequence[str]) -> list[Fold]:
    """Mỗi nhóm làm test đúng một lần; thứ tự theo tên nhóm nên chạy lại ra y hệt."""
    names = sorted(set(groups))
    if len(names) < 2:
        raise ValueError(f"cần ít nhất 2 nhóm để kiểm định chéo, đang có {len(names)}")
    return [
        Fold(
            test_group=g,
            train=tuple(i for i, x in enumerate(groups) if x != g),
            test=tuple(i for i, x in enumerate(groups) if x == g),
        )
        for g in names
    ]


def error_counts(
    rows: Sequence[RepRow], groups: Sequence[str], error_labels: Sequence[str]
) -> dict[str, dict[str, int]]:
    """{nhóm: {"reps": số rep, <lỗi>: số rep có lỗi đó}}."""
    counts: dict[str, dict[str, int]] = {}
    for r, g in zip(rows, groups, strict=True):
        c = counts.setdefault(g, {"reps": 0, **{e: 0 for e in error_labels}})
        c["reps"] += 1
        for e in r.errors:
            c[e] += 1
    return dict(sorted(counts.items()))


def missing_errors(counts: dict[str, dict[str, int]], error_labels: Sequence[str]) -> list[str]:
    """Cảnh báo nhóm thiếu hẳn một lỗi: lấy nhóm đó làm test thì không đo được recall lỗi đó."""
    return [f"{g}: không có rep {e}" for g, c in counts.items() for e in error_labels if c[e] == 0]
