import re

_CORRECTION_MARKER = re.compile(
    r"\b(?:i mean|i meant|actually|rather|instead|forget|ignore|remove|drop|"
    r"exclude|omit|focus only)\b",
    re.I,
)
_NEGATION = re.compile(
    r"\b(?:not(?!\s+only)|never|no longer|without|forget|ignore|remove|drop|"
    r"exclude|omit)\b(?:\s+[\w'-]+){0,3}\s*$",
    re.I,
)


def has_correction_marker(text: str) -> bool:
    return bool(_CORRECTION_MARKER.search(text))


def is_negated_source_span(text: str, span: tuple[int, int]) -> bool:
    delimiters = ".;!?,\n"
    boundary = max(text.rfind(delimiter, 0, span[0]) for delimiter in delimiters)
    prefix = text[boundary + 1 : span[0]]
    return bool(_NEGATION.search(prefix))


def validate_source_span(
    source_text: str | None,
    span: tuple[int, int] | None,
    evidence: str | None = None,
) -> None:
    if span is None:
        return
    if source_text is None:
        raise ValueError("A source span requires its source text.")
    if (
        len(span) != 2
        or type(span[0]) is not int
        or type(span[1]) is not int
        or span[0] < 0
        or span[1] <= span[0]
        or span[1] > len(source_text)
    ):
        raise ValueError(f"Invalid half-open source span: {span!r}.")
    if evidence is not None and source_text[slice(*span)] != evidence:
        raise ValueError("The source span does not select the declared evidence.")
