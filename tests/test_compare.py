from pathlib import Path

import pytest

import evaluation.compare as compare
from evaluation.baseline import MAIN_ERRORS, summarize
from evaluation.compare import main as compare_main
from evaluation.compare import parse_models, summary_table
from evaluation.cross_validate import FoldResult, cross_validate
from evaluation.split import evaluation_rows, group_keys
from formcoach.dataset import build_dataset
from formcoach.exercises import PushUp
from formcoach.models import make_classifier
from tests.test_dataset import add_session


def make_data(tmp_path: Path) -> None:
    # 3 buổi × 3 rep, khuỷu xuống 70° > 67° → luật luôn báo shallow (đúng ở a, c; nhầm ở b).
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))
    add_session(tmp_path, "b_pushup", "2026-10-21T14:00:00+07:00")
    add_session(tmp_path, "c_pushup", "2026-10-22T08:00:00+07:00", ("shallow",))
    # Hiệp quay thử (ngưỡng chọn từ đó) không được tính vào phần chấm điểm.
    add_session(tmp_path, "2026-10-20T10-14-01_pushup", "2026-10-20T10:14:01+07:00", ("shallow",))


def test_parse_models_cleans_dedups_and_validates() -> None:
    assert parse_models(" rules , rules ") == ["rules"]
    with pytest.raises(ValueError, match="khong_co"):
        parse_models("rules,khong_co")
    with pytest.raises(ValueError):
        parse_models(" , ")


def test_rules_row_equals_baseline_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_data(tmp_path)
    compare_main(["--data", str(tmp_path), "--models", "rules"])
    out = capsys.readouterr().out

    # Số mong đợi tính độc lập bằng chính hàm của baseline trên cùng dữ liệu.
    ds = build_dataset(tmp_path, "pushup")
    rows = evaluation_rows(ds)
    results = cross_validate(
        lambda: make_classifier("rules", PushUp()), rows, group_keys(rows, "block")
    )
    spread_text, macro, exact = summarize(results, MAIN_ERRORS["pushup"])
    row = next(x for x in out.splitlines() if x.strip().startswith("rules") and "macro" not in x)
    assert f"{macro:.2f}" in row and f"{exact:.2f}" in row and str(spread_text) in row
    assert f"{macro:.2f}" == "0.80"  # shallow: 6 đúng, 3 nhầm → P 0,67, R 1 → F1 0,80
    assert f"{exact:.2f}" == "0.67"  # 6/9 rep đoán đúng toàn bộ tập lỗi


def test_output_has_per_model_report_and_summary_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_data(tmp_path)
    compare_main(["--data", str(tmp_path)])  # mặc định: rules
    out = capsys.readouterr().out
    assert "=== Mô hình: rules ===" in out
    assert "So sánh mô hình" in out and "macro-F1 gộp" in out
    assert "neck_drop*" in out  # thử nghiệm: có cột riêng, không tính vào macro-F1
    assert "9 rep, 3 lần chia" in out  # 3 hiệp × 3 rep, mỗi buổi một lần chia


def test_unknown_model_is_rejected_before_any_work(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="khong_co"):
        compare_main(["--data", str(tmp_path), "--models", "khong_co"])


def test_not_enough_groups(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00")
    compare_main(["--data", str(tmp_path)])
    assert "Chưa đủ dữ liệu" in capsys.readouterr().out


def test_a_fresh_model_is_built_for_every_fold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Luật không có trạng thái nên dùng chung một mô hình không đổi kết quả; kiểm tra thẳng việc
    # registry được gọi mỗi lần chia (RF/stump có trạng thái: dùng chung = rò rỉ giữa các lần chia).
    make_data(tmp_path)
    built: list[object] = []
    real = compare.make_classifier

    def spy(name, exercise, seed=0):
        model = real(name, exercise, seed)
        built.append(model)
        return model

    monkeypatch.setattr(compare, "make_classifier", spy)
    compare_main(["--data", str(tmp_path), "--models", "rules"])
    capsys.readouterr()
    assert len(built) == 3 and len({id(m) for m in built}) == 3  # 3 lần chia, 3 mô hình riêng


def fold(true: list[set[str]], pred: list[set[str]]) -> FoldResult:
    t, p = [frozenset(x) for x in true], [frozenset(x) for x in pred]
    return FoldResult("g", tuple(range(len(t))), tuple(t), tuple(p))


def test_macro_f1_column_ignores_experimental_errors() -> None:
    # shallow đoán đúng hết (F1 1,0); neck_drop (thử nghiệm) đoán sai hết (F1 0,0).
    # Nếu neck_drop lọt vào macro-F1 thì cột này ra 0,50 thay vì 1,00.
    results = {
        "rules": [fold([{"shallow", "neck_drop"}, set()], [{"shallow"}, {"neck_drop"}])],
    }
    table = summary_table(results, ("shallow",), ("neck_drop",))
    row = next(x for x in table.splitlines() if x.strip().startswith("rules"))
    assert row.split()[1] == "1.00"  # F1 shallow
    assert row.split()[2] == "0.00"  # F1 neck_drop*: có cột riêng
    assert row.split()[3] == "1.00"  # macro-F1 gộp: chỉ lỗi chính


def test_stump_run_prints_learned_thresholds_next_to_hand_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_data(tmp_path)  # khuỷu luôn 70° → mọi giá trị bằng nhau → không có ngưỡng nào để học
    compare_main(["--data", str(tmp_path), "--models", "rules,stump"])
    out = capsys.readouterr().out
    assert "=== Mô hình: stump ===" in out
    assert "Ngưỡng học theo từng lần chia" in out
    hand = next(x for x in out.splitlines() if x.strip().startswith("ngưỡng chọn tay"))
    assert "> 67" in hand and "< 146" in hand and "< 128" in hand
    assert "test 2026-10-21#1" in out and "test 2026-10-22#1" in out
    assert out.count("Ngưỡng học theo từng lần chia") == 1  # chỉ mô hình có ngưỡng học
    # Không học được ngưỡng nào: phải nói rõ thay vì lặng lẽ cho F1 = 0.
    assert "CẢNH BÁO: lần chia test 2026-10-21#1: không fit được" in out
    row = next(x for x in out.splitlines() if x.strip().startswith("stump") and "macro" not in x)
    # Không học được ngưỡng nào → không bao giờ báo: chỉ 3 rep không lỗi (buổi b) đúng → 3/9.
    assert row.split()[-1] == "0.33"


def test_three_models_run_in_one_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make_data(tmp_path)
    compare_main(
        ["--data", str(tmp_path), "--models", "rules,stump,rf", "--boot", "0", "--seed-runs", "0"]
    )
    out = capsys.readouterr().out
    for name in ("rules", "stump", "rf"):
        assert f"=== Mô hình: {name} ===" in out
    table = out.split("So sánh mô hình")[1].splitlines()
    rows = [x.split()[0] for x in table if x.strip() and not x.strip().startswith(("mô hình",))]
    assert rows[-3:] == ["rules", "stump", "rf"]  # cùng một bảng, đúng thứ tự yêu cầu


def test_ci_table_verdict_follows_the_preregistered_rule() -> None:
    from evaluation.compare import ci_table

    truth = [{"shallow"}] * 20 + [set()] * 20
    wrong = [set()] * 20 + [{"shallow"}] * 20  # luôn sai
    better = {"rules": [fold(truth, wrong)], "rf": [fold(truth, truth)]}
    out = ci_table(better, ("shallow",), n_boot=100, seed=0, reference="rules")
    assert "rf: cao hơn rules (khoảng của hiệu không chứa 0)" in out
    assert "(mốc so sánh)" in out and "LẠC QUAN" in out
    same = {"rules": [fold(truth, wrong)], "rf": [fold(truth, wrong)]}
    out = ci_table(same, ("shallow",), n_boot=100, seed=0, reference="rules")
    assert "rf: chưa có bằng chứng khác rules (khoảng của hiệu chứa 0)" in out


def test_ci_table_rejects_models_with_different_truth() -> None:
    from evaluation.compare import ci_table

    a = {"rules": [fold([{"shallow"}], [set()])], "rf": [fold([set()], [set()])]}
    with pytest.raises(ValueError, match="không khớp"):
        ci_table(a, ("shallow",), n_boot=5, seed=0, reference="rules")


def test_seed_and_importance_tables() -> None:
    from evaluation.compare import importance_table, seed_table

    out = seed_table("rf", [(0, 0.80, 0.70), (1, 0.82, 0.72)])
    assert "seed 0..1" in out and "0.81 ± 0.01" in out
    imps = [
        {"shallow": {"a": 0.6, "b": 0.4}, "hip_sag": {"a": 1.0, "b": 0.0}},
        {"shallow": {"a": 0.2, "b": 0.8}},  # lần chia này không có rừng hip_sag
    ]
    out = importance_table(imps, ["shallow", "hip_sag", "neck_drop"], top=1)
    assert "shallow" in out and "b 0.60" in out  # (0,4 + 0,8) / 2 → b đứng đầu
    assert "a 0.50" in next(x for x in out.splitlines() if x.strip().startswith("hip_sag"))
    assert "không có rừng nào được fit" in out  # neck_drop


def test_full_run_prints_ci_seed_and_importance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_data(tmp_path)
    args = ["--data", str(tmp_path), "--models", "rules,rf", "--boot", "30", "--seed-runs", "2"]
    compare_main(args)
    out = capsys.readouterr().out
    assert "Khoảng tin cậy 95%" in out and "bootstrap 30 lần" in out
    assert "Độ lệch do seed — rf chạy seed 0..1" in out
    assert "Độ quan trọng đặc trưng" in out
    assert "Độ lệch do seed — rules" not in out  # luật không có ngẫu nhiên


def test_ci_table_lists_per_fold_differences() -> None:
    from evaluation.compare import ci_table

    truth = [{"shallow"}] * 4 + [set()] * 4
    wrong = [set()] * 4 + [{"shallow"}] * 4
    good = {
        "rules": [fold(truth, wrong), fold(truth, truth)],
        "rf": [fold(truth, truth), fold(truth, truth)],
    }
    out = ci_table(good, ("shallow",), n_boot=20, seed=0, reference="rules")
    line = next(x for x in out.splitlines() if x.strip().startswith("rf: g:"))
    assert "+1.00" in line and "+0.00" in line and "(1/2 lần chia cao hơn)" in line


def test_importance_table_tags_experimental_errors() -> None:
    from evaluation.compare import importance_table

    imps = [{"shallow": {"a": 1.0}, "neck_drop": {"b": 1.0}}]
    out = importance_table(imps, ["shallow", "neck_drop"], experimental=("neck_drop",))
    assert any(x.strip().startswith("neck_drop*") for x in out.splitlines())
    assert not any(x.strip().startswith("shallow*") for x in out.splitlines())
    assert "* = thử nghiệm" in out
