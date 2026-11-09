from app.sense.intent.subintent.models import SubIntentType


# Ordered by specificity; multiple matched categories are retained.
SUBINTENT_CUES = (
    (SubIntentType.GREETING, (r"^(?:hi|hello|hey|good morning|good afternoon|good evening)\b",)),
    (SubIntentType.FAREWELL, (r"\b(?:goodbye|bye|farewell|see you|talk to you later)\b",)),
    (SubIntentType.CLARIFICATION, (r"\b(?:clarify|could you explain what you mean|what do you mean|can you be more specific)\b",)),
    (SubIntentType.FOLLOW_UP, (r"\b(?:follow[ -]?up|what about|how about|and regarding)\b",)),
    (SubIntentType.CONTINUATION, (r"\b(?:continue|go on|carry on|keep going|pick up where)\b",)),
    (SubIntentType.CORRECTION, (r"\b(?:correct that|fix (?:the|this|that)|that's incorrect|that is incorrect|i meant)\b",)),
    (SubIntentType.CONFIRMATION, (r"^(?:yes|yeah|yep|correct|confirmed|that's right|that is right)\b", r"\b(?:confirm|please confirm)\b")),
    (SubIntentType.NEGATION, (r"^(?:no|nope|not at all)\b", r"\b(?:do not|don't|cannot|can't|never mind|not that)\b")),
    (SubIntentType.ALERT, (r"\b(?:alert|notify|notification)\b",)),
    (SubIntentType.MONITORING, (r"\b(?:monitor|track|watch)\b",)),
    (SubIntentType.DECISION_SUPPORT, (r"\b(?:should i|help me decide|recommend|which should|make a decision|advise me|what should i investigate)\b",)),
    (SubIntentType.PLANNING, (r"\b(?:plan|planning|strategy|roadmap|schedule)\b",)),
    (SubIntentType.CREATION, (r"\b(?:create|make\b(?!\s+it\s+(?:shorter|briefer|narrower|broader))|build|write|draft|generate|design)\b",)),
    (SubIntentType.MODIFICATION, (r"\b(?:modify|change|update|edit|revise|amend|shorten|shorter|briefer|expand|narrow|narrower|broaden|broader)\b",)),
    (SubIntentType.CALCULATION, (r"\b(?:calculate|compute|work out|what is the return|how much (?:would|will|does))\b",)),
    (SubIntentType.COMPARISON, (r"\b(?:compare|comparison|versus|vs\.?|against|difference between)\b",)),
    (SubIntentType.ANALYSIS, (r"\b(?:analy[sz]e|analysis|assess|evaluate)\b",)),
    (SubIntentType.RESEARCH, (r"(?:^|\b(?:please|pls|actually,?|can you|can u|could you|would you|then|and|no,?\s+|i need to|i want to|i'd like to)\s+)(?:research|investigate|check|look\s+into)\b|\b(?:look up|find sources|gather information)\b|^\s*abeg\s+check\b",)),
    (SubIntentType.PREDICTION, (r"\b(?:predict|forecast|project|outlook|what will .* do|what (?:would|will) happen if|what happens if|expected to)\b",)),
    (SubIntentType.EXPLANATION, (r"\b(?:explain|why\s+(?:did|is|does|has|have|was|were|are|do|will|would)?|how does|how do|how did|how has|how have)\b",)),
    (SubIntentType.INFORMATION, (r"^(?:what|who|where|when|which|tell me about|define|give me)\b", r"\b(?:information about|facts about|i need to know what|i want to know what|what is driving|what's driving|what is going on|what's going on)\b")),
)

ACTION_SUBINTENTS = frozenset({
    SubIntentType.ALERT, SubIntentType.MONITORING,
    SubIntentType.DECISION_SUPPORT, SubIntentType.PLANNING, SubIntentType.CREATION,
    SubIntentType.MODIFICATION, SubIntentType.CALCULATION, SubIntentType.COMPARISON,
    SubIntentType.ANALYSIS, SubIntentType.RESEARCH, SubIntentType.PREDICTION,
    SubIntentType.EXPLANATION,
})