"""Test khung: chứng minh pytest chạy được và các lớp abstract đúng là abstract."""

import numpy as np
import pytest

from formcoach.coach import Coach
from formcoach.exercises import Exercise
from formcoach.models import FormClassifier
from formcoach.pose import PoseEstimator
from formcoach.types import PoseSequence


def test_pose_sequence_holds_data() -> None:
    pose = PoseSequence(
        keypoints=np.zeros((2, 3, 3)),
        joint_names=["hip", "knee", "ankle"],
        fps=30.0,
        frame_size=(1920, 1080),
    )
    assert pose.keypoints.shape == (2, 3, 3)


@pytest.mark.parametrize("abstract_cls", [Exercise, PoseEstimator, FormClassifier, Coach])
def test_abstract_classes_cannot_be_instantiated(abstract_cls: type) -> None:
    with pytest.raises(TypeError):
        abstract_cls()
