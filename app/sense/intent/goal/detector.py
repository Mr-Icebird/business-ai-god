import re

from app.sense.intent.goal.models import GoalDetectionResult, UserGoal
from app.sense.intent.models import ConfidenceLevel


_GOAL_CUES = (
    (UserGoal.TRADING_RESEARCH, r"\b(?:trading|trade) (?:research|strategy|plan)\b|\binvestigating a trading strategy\b"),
    (UserGoal.INVESTMENT_RESEARCH, r"\b(?:investment|investing) research\b|\bfor (?:an? )?investment\b"),
    (UserGoal.BUSINESS_RESEARCH, r"\b(?:business|market) research\b|\bfor (?:my )?business\b"),
    (UserGoal.LEARNING, r"\b(?:i am learning|i'm learning|to learn|for learning|teach me|studying)\b"),
    (UserGoal.MONITORING, r"\b(?:monitor|track|watch)\b"),
    (UserGoal.DECISION_SUPPORT, r"\b(?:should i|help me decide|recommend|which should|make a decision)\b"),
    (UserGoal.CURRENT_INFORMATION, r"\b(?:today|right now|currently|latest|current|this week)\b"),
    (UserGoal.RESEARCH, r"\b(?:research|investigate|find out|look up)\b"),
    (UserGoal.GENERAL_CURIOSITY, r"\b(?:curious|just wondering|out of curiosity)\b"),
)


class GoalDetector:
    def detect(self, text: str) -> GoalDetectionResult:
        matches = [goal for goal, pattern in _GOAL_CUES if re.search(pattern, text, re.IGNORECASE)]
        if not matches:
            return GoalDetectionResult()
        return GoalDetectionResult(
            primary=matches[0], detected=tuple(dict.fromkeys(matches)),
            confidence=ConfidenceLevel.HIGH if matches[0] in {
                UserGoal.TRADING_RESEARCH, UserGoal.INVESTMENT_RESEARCH,
                UserGoal.BUSINESS_RESEARCH, UserGoal.LEARNING,
                UserGoal.GENERAL_CURIOSITY,
            } else ConfidenceLevel.MEDIUM,
        )