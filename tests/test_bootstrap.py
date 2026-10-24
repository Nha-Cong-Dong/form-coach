import pytest

from evaluation.metrics import (
    bootstrap_macro_f1,
    paired_differences,
    percentile_interval,
)

ERRORS = ("shallow", "hip_sag")


def fs(*names: str) -> frozenset[str]:
    return frozenset(names)


# 40 rep: một nửa có shallow, một nửa có hip_sag (mỗi lỗi 20 rep dương).
TRUTH = [fs("shallow")] * 20 + [fs("hip_sag")] * 20
# "Luôn sai": đổi lỗi này thành lỗi kia → mọi rep vừa bỏ sót vừa báo nhầm → F1 = 0.
WRONG = [fs("hip_sag")] * 20 + [fs("shallow")] * 20


def test_percentile_interval_of_known_values() -> None:
    iv = percentile_interval(list(range(101)), level=0.90)  # 0, 1, ..., 100
    assert (iv.low, iv.high, iv.n) == (pytest.approx(5.0), pytest.approx(95.0), 101)


def test_percentile_interval_interpolates_and_drops_none() -> None:
    iv = percentile_interval([None, 0.0, 10.0, None], level=0.5)  # còn [0, 10]
    assert (iv.low, iv.high, iv.n) == (pytest.approx(2.5), pytest.approx(7.5), 2)
    assert percentile_interval([None, None]) is None


def test_paired_differences_skips_undefined_pairs() -> None:
    assert paired_differences([1.0, None, 0.5, 0.2], [0.5, 0.1, None, 0.2]) == [0.5, 0.0]
    with pytest.raises(ValueError):
        paired_differences([1.0], [1.0, 2.0])


def test_identical_predictions_give_difference_exactly_zero() -> None:
    samples = bootstrap_macro_f1(TRUTH, {"a": TRUTH, "b": list(TRUTH)}, ERRORS, n_boot=50)
    diffs = paired_differences(samples["a"], samples["b"])
    assert len(diffs) == 50 and set(diffs) == {0.0}  # cùng mẫu cho cả hai → hiệu luôn 0
    iv = percentile_interval(diffs)
    assert (iv.low, iv.high) == (0.0, 0.0)


def test_perfect_vs_always_wrong_interval_is_entirely_above_zero() -> None:
    samples = bootstrap_macro_f1(TRUTH, {"perfect": TRUTH, "wrong": WRONG}, ERRORS, n_boot=200)
    assert set(samples["perfect"]) == {1.0} and set(samples["wrong"]) == {0.0}
    iv = percentile_interval(paired_differences(samples["perfect"], samples["wrong"]))
    assert (iv.low, iv.high) == (1.0, 1.0)  # hiệu luôn 1: khoảng nằm hẳn trên 0


def test_same_seed_same_result_and_other_seed_differs() -> None:
    noisy = [fs("shallow") if i % 3 == 0 else fs() for i in range(40)]  # đúng một phần
    run = lambda seed: bootstrap_macro_f1(TRUTH, {"m": noisy}, ERRORS, n_boot=100, seed=seed)  # noqa: E731
    assert run(1) == run(1)
    assert run(1) != run(2)


def test_resamples_with_replacement_from_the_given_reps() -> None:
    # 1 rep lỗi + 3 rep sạch, mô hình hoàn hảo: F1 là 1 nếu mẫu có rep lỗi, None nếu không
    # (không có lỗi thật và không báo → không xác định, KHÔNG phải 0). Với 4 rep bốc có hoàn lại,
    # có lần không bốc trúng rep lỗi: phải thấy None, và các lần còn lại đều là 1.
    truth = [fs("shallow"), fs(), fs(), fs()]
    samples = bootstrap_macro_f1(truth, {"m": truth}, ("shallow",), n_boot=200)["m"]
    assert None in samples and {v for v in samples if v is not None} == {1.0}


def test_all_undefined_gives_no_interval() -> None:
    clean = [fs()] * 10  # không có lỗi thật, mô hình cũng không báo → mọi lần đều None
    samples = bootstrap_macro_f1(clean, {"m": clean}, ERRORS, n_boot=20)["m"]
    assert samples == [None] * 20
    assert percentile_interval(samples) is None


def test_length_mismatch_and_empty_are_rejected() -> None:
    with pytest.raises(ValueError, match="m"):
        bootstrap_macro_f1(TRUTH, {"m": TRUTH[:-1]}, ERRORS, n_boot=5)
    with pytest.raises(ValueError):
        bootstrap_macro_f1([], {"m": []}, ERRORS, n_boot=5)
