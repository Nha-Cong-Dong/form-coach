"""Lưu bộ phân loại đã huấn luyện ra file và đọc lại (D1: server không có `data/` để tự train).

Train ở máy (có `data/`, có đánh giá) → `python -m formcoach train` lưu file → tải file lên server →
server đọc bằng `load_model`. Mô hình server dùng chính là mô hình đã được đánh giá.

File là pickle kèm thông tin (`ModelInfo`). Lúc đọc kiểm tra: đúng định dạng, đúng bài tập, CÙNG
phiên bản scikit-learn (pickle của bản này có thể đọc lỗi hoặc đọc sai ở bản khác). Sai thì báo
`ModelFileError` rõ ràng, không âm thầm lùi về luật.

AN TOÀN: mở một file pickle có thể chạy mã trong file. Chỉ đọc file do chính mình tạo; không bao
giờ cho người dùng tải file mô hình lên. Không commit file mô hình (CLAUDE.md).
"""

from __future__ import annotations

import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import sklearn

from formcoach.models.base import FormClassifier

FORMAT_VERSION = 1


class ModelFileError(Exception):
    """File mô hình không dùng được: hỏng, sai định dạng, sai bài tập hoặc khác bản scikit-learn."""


@dataclass(frozen=True)
class ModelInfo:
    model_name: str  # rf, stump, rules (tên trong registry)
    exercise: str
    n_reps: int  # số rep đã gán nhãn dùng để huấn luyện
    trained_at: str  # ISO 8601
    sklearn_version: str


def save_model(path: Path, classifier: FormClassifier, info: ModelInfo) -> None:
    """Ghi file mô hình (tạo thư mục nếu chưa có). Ghi ra file tạm rồi đổi tên: lỗi giữa chừng
    không để lại file dở dang ở đúng tên mà server sẽ đọc."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format_version": FORMAT_VERSION, "info": asdict(info), "classifier": classifier}
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def load_model(path: Path, exercise: str) -> tuple[FormClassifier, ModelInfo]:
    """Đọc file do `save_model` ghi. Mọi sai lệch → ModelFileError nói rõ sai ở đâu."""
    path = Path(path)
    try:
        with path.open("rb") as f:
            payload: Any = pickle.load(f)
    except FileNotFoundError:
        raise ModelFileError(f"không thấy file mô hình {path}") from None
    except Exception as e:  # noqa: BLE001 - file hỏng / không phải pickle: báo chung một lỗi
        raise ModelFileError(f"không đọc được file mô hình {path}: {e}") from None

    if not isinstance(payload, dict) or payload.get("format_version") != FORMAT_VERSION:
        raise ModelFileError(
            f"{path} không phải file mô hình Form Coach (định dạng {FORMAT_VERSION})"
        )
    try:
        info = ModelInfo(**payload["info"])
    except (KeyError, TypeError) as e:
        raise ModelFileError(f"{path}: thông tin mô hình hỏng ({e})") from None
    if info.exercise != exercise:
        raise ModelFileError(f"{path} là mô hình bài {info.exercise!r}, không phải {exercise!r}")
    if info.sklearn_version != sklearn.__version__:
        raise ModelFileError(
            f"{path} được lưu bằng scikit-learn {info.sklearn_version}, máy này có "
            f"{sklearn.__version__}: cài đúng bản trong requirements.txt rồi train lại"
        )
    classifier = payload.get("classifier")
    if not isinstance(classifier, FormClassifier):
        raise ModelFileError(f"{path}: không có bộ phân loại trong file")
    return classifier, info
