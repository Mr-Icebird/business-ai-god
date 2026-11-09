from app.sense.intent.detection.models import IntentType


INTENT_HIERARCHY = {
    IntentType.INFORMATION: ("knowledge", "information"),
    IntentType.ANALYSIS: ("knowledge", "analysis"),
    IntentType.RESEARCH: ("knowledge", "research"),
    IntentType.EXPLANATION: ("knowledge", "explanation"),
    IntentType.COMPARISON: ("knowledge", "comparison"),
    IntentType.CALCULATION: ("knowledge", "calculation"),
    IntentType.PREDICTION: ("knowledge", "prediction"),
    IntentType.PLANNING: ("task", "planning"),
    IntentType.DECISION_SUPPORT: ("task", "decision_support"),
    IntentType.MONITORING: ("task", "monitoring"),
    IntentType.ALERT: ("task", "alert"),
    IntentType.CREATION: ("task", "creation"),
    IntentType.MODIFICATION: ("task", "modification"),
    IntentType.CORRECTION: ("interaction", "correction"),
    IntentType.CONFIRMATION: ("interaction", "confirmation"),
    IntentType.NEGATION: ("interaction", "negation"),
    IntentType.CLARIFICATION: ("interaction", "clarification"),
    IntentType.FOLLOW_UP: ("interaction", "follow_up"),
    IntentType.CONTINUATION: ("interaction", "continuation"),
    IntentType.GREETING: ("social", "greeting"),
    IntentType.FAREWELL: ("social", "farewell"),
    IntentType.EXECUTION: ("task", "execution"),
}