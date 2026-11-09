from app.sense.intent.action.models import ActionDetectionResult, ActionType


_OUTPUTS = {
    ActionType.EXPLAIN: "explanation",
    ActionType.CALCULATE: "calculation result",
    ActionType.RESEARCH: "research findings",
    ActionType.COMPARE: "comparison",
    ActionType.ANALYZE: "analysis",
    ActionType.PLAN: "plan",
    ActionType.CREATE: "created content",
    ActionType.MODIFY: "modified content",
    ActionType.MONITOR: "monitoring status",
    ActionType.ALERT: "alert criteria or notification",
    ActionType.EXECUTE: "execution result",
}


class TaskPlanner:
    """Provides lightweight expected outputs; it does not execute tasks."""

    def plan(self, actions: ActionDetectionResult) -> tuple[tuple[str, ...], str | None]:
        outputs = tuple(dict.fromkeys(
            _OUTPUTS[action] for action in actions.actions if action in _OUTPUTS
        ))
        if not outputs:
            return (), None
        return outputs, "The requested operation is completed and its output is provided."