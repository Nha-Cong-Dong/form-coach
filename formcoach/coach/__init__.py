"""Coach: Coach (lớp gốc), TemplateCoach, build_coach_prompt (prompt cho ClaudeCoach ở backend/)."""

from formcoach.coach.base import Coach, CoachProgress, progress_after
from formcoach.coach.template import TemplateCoach

__all__ = ["Coach", "CoachProgress", "TemplateCoach", "progress_after"]
