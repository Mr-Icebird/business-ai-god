import re
from dataclasses import replace

from app.sense.intent.constraints.models import (
    ConstraintDetectionResult,
    ConstraintType,
    TaskConstraint,
)
from app.sense.intent.models import ConfidenceLevel


_RULES = (
    (ConstraintType.TIME, r"\b(?:use|in|from|with|than)\s+\d{4}(?:\s+data)?\b|\b(?:before|after|since)\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b|\b(?:19|20)\d{2}\b|\b(?:the\s+)?(?:last|past)\s+\d+\s+(?:days?|weeks?|months?|years?)\b|\b(?:today|yesterday|tomorrow)\b|\b(?:before|after|since|within)\s+(?:\d{4}|the\s+announcement|\d+\s+(?:days?|weeks?|months?|years?))\b"),
    (ConstraintType.GEOGRAPHIC, r"\b(?:in|for|focus on)\s+(?:the\s+)?(?:US|U\.S\.|United States|Nigeria|Ghana|Kenya|Europe|Africa|African|Asia|China|India|UK|United Kingdom)(?:\s+markets?)?(?:\s+only)?\b|\b(?:Nigeria|Ghana|Kenya|Europe|Africa|African|Asia|China|India|US|U\.S\.)(?:\s+markets?)?\s+only\b"),
    (ConstraintType.FINANCIAL, r"\b(?:under|below|above|over|at most|no more than|budget of|with a budget of|risk no more than|market cap above)\s+[$₦€£]?\s?\d[\d,.]*(?:\s?(?:%|billion|million|bn|m))?|\bwith\s+(?:a\s+)?[$₦€£]\s?\d[\d,.]*\s+budget\b"),
    (ConstraintType.DATA, r"\b(?:use|using)\s+(?:official sources only|historical data|live data|the data i provided|provided data)\b|\b(?:historical data|live data)\b|\b(?:don't|do not)\s+use\s+(?:social media|unofficial sources|external data)\b"),
    (ConstraintType.OUTPUT_FORMAT, r"\b(?:give me|return|make it|provide|format as)\s+(?:a\s+)?(?:table|json|pdf|csv|bullet points?|shorter|briefer|concise)\b|\b(?:keep it short|keep it brief|briefly|in one paragraph|explain it like i(?:'| a)m?\s*\d+)\b"),
    (ConstraintType.SCOPE, r"\b(?:focus on|only include|compare only|exclude|don't include|do not include)\s+[^,.;!?]+|\b(?!I\b|we\b|you\b|they\b|he\b|she\b|it\b)[A-Za-z0-9][\w.-]*(?:\s+[A-Za-z0-9][\w.-]*)?\s+only\b"),
    (ConstraintType.USER_SPECIFIED, r"\b(?:without|do not|don't|must not|avoid)\s+(?:making recommendations|recommendations|investment advice|personal data|speculation)\b"),
    (ConstraintType.USER_SPECIFIED, r"\b(?:without|do not|don't|must not|avoid)\s+[^,.;!?]+"),
)
_SOFT = re.compile(r"\b(?:prefer|if possible|ideally|keep it short|briefly)\b", re.IGNORECASE)
_HARD = re.compile(r"\b(?:only|must|do not|don't|must not|no more than|at most|under|below|above|exclude)\b", re.IGNORECASE)
_REQUEST_CUE = re.compile(
    r"^\s*(?:please|pls|can you|could you|would you|research|investigate|analy[sz]e|compare|calculate|compute|explain|plan|create|build|write|draft|monitor|track|alert|execute|use|focus on|limit to|restrict to|for the)\b",
    re.IGNORECASE,
)
_EXPLICIT_LIMIT = re.compile(
    r"\b(?:only|focus on|limit to|restrict to|before|after|since|within|last|past|today|yesterday|tomorrow)\b",
    re.IGNORECASE,
)


class ConstraintDetector:
    def detect(self, text: str) -> ConstraintDetectionResult:
        candidates: list[tuple[int, int, ConstraintType, str]] = []
        for constraint_type, pattern in _RULES:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group().strip()
                if constraint_type == ConstraintType.GEOGRAPHIC:
                    location_only = value.casefold().startswith(("in ", "for "))
                    if location_only and not _REQUEST_CUE.search(text) and not _EXPLICIT_LIMIT.search(value):
                        continue
                if constraint_type == ConstraintType.TIME:
                    year_only = bool(re.fullmatch(
                        r"(?:(?:in|from|with|than)\s+)?(?:19|20)\d{2}", value
                    ))
                    if year_only and not _REQUEST_CUE.search(text) and not _EXPLICIT_LIMIT.search(value):
                        continue
                candidates.append((match.start(), match.end(), constraint_type, value))
        candidates.sort(key=lambda item: (item[0], item[1]))

        unique = []
        seen = set()
        accepted_spans: list[tuple[int, int]] = []
        for start, end, kind, value in candidates:
            if any(
                start < existing_end and existing_start < end
                for existing_start, existing_end in accepted_spans
            ):
                continue
            key = (kind, value.casefold())
            if key in seen:
                continue
            seen.add(key)
            snippet = text[max(0, start - 12):min(len(text), end + 12)]
            operator = self._operator(value)
            hard = True if _HARD.search(snippet) else False if _SOFT.search(snippet) else None
            unique.append(TaskConstraint(
                constraint_id=f"constraint-{len(unique) + 1}",
                constraint_type=kind,
                value=value,
                operator=operator,
                source_text=text[start:end],
                source_span=(start, end),
                confidence=ConfidenceLevel.HIGH,
                is_hard=hard,
            ))
            accepted_spans.append((start, end))

        conflicts: dict[str, set[str]] = {item.constraint_id: set() for item in unique}
        for index, left in enumerate(unique):
            for right in unique[index + 1:]:
                left_key = self._conflict_key(left)
                right_key = self._conflict_key(right)
                if (
                    left_key is not None
                    and right_key is not None
                    and left_key[0] == right_key[0]
                    and left_key[1] != right_key[1]
                    and not (
                        left_key[0] == "time_year"
                        and re.search(r"\b(?:compare|versus|vs\.?|between)\b", text, re.IGNORECASE)
                    )
                ):
                    conflicts[left.constraint_id].add(right.constraint_id)
                    conflicts[right.constraint_id].add(left.constraint_id)
        resolved = tuple(
            replace(item, conflicts_with=tuple(sorted(conflicts[item.constraint_id])))
            for item in unique
        )
        return ConstraintDetectionResult(
            constraints=resolved,
            has_conflicts=any(item.conflicts_with for item in resolved),
        )

    def combine(
        self,
        previous: ConstraintDetectionResult | None,
        current: ConstraintDetectionResult,
        *,
        text: str = "",
    ) -> ConstraintDetectionResult:
        if previous is None or not previous.constraints:
            return current
        combined = []
        seen = set()
        for item in previous.constraints + current.constraints:
            key = (item.constraint_type, item.value.casefold())
            if key in seen:
                continue
            seen.add(key)
            combined.append(replace(
                item,
                constraint_id=f"constraint-{len(combined) + 1}",
                conflicts_with=(),
            ))

        conflicts: dict[str, set[str]] = {item.constraint_id: set() for item in combined}
        compare_periods = bool(re.search(r"\b(?:compare|versus|vs\.?|between)\b", text, re.IGNORECASE))
        for index, left in enumerate(combined):
            for right in combined[index + 1:]:
                left_key = self._conflict_key(left)
                right_key = self._conflict_key(right)
                if (
                    left_key is None or right_key is None
                    or left_key[0] != right_key[0]
                    or left_key[1] == right_key[1]
                    or compare_periods and left_key[0] == "time_year"
                ):
                    continue
                conflicts[left.constraint_id].add(right.constraint_id)
                conflicts[right.constraint_id].add(left.constraint_id)
        resolved = tuple(
            replace(item, conflicts_with=tuple(sorted(conflicts[item.constraint_id])))
            for item in combined
        )
        return ConstraintDetectionResult(
            constraints=resolved,
            has_conflicts=any(item.conflicts_with for item in resolved),
        )

    @staticmethod
    def _operator(value: str) -> str | None:
        match = re.search(r"\b(before|after|since|within|under|below|above|over|at most|no more than|exclude|avoid|don't include|do not include)\b", value, re.IGNORECASE)
        if match:
            return match.group(1).casefold()
        return "budget" if "budget" in value.casefold() else None

    @staticmethod
    def _conflict_key(constraint: TaskConstraint) -> tuple[str, str] | None:
        value = constraint.value.casefold()
        if constraint.constraint_type == ConstraintType.DATA:
            if "live data" in value:
                return "data_mode", "live"
            if "historical data" in value:
                return "data_mode", "historical"
        if constraint.constraint_type == ConstraintType.TIME:
            year = re.search(r"\b(?:19|20)\d{2}\b", value)
            if year:
                return "time_year", year.group()
        if constraint.constraint_type == ConstraintType.SCOPE:
            match = re.search(r"(?:exclude|don't include|do not include)\s+(\w+)|\b(\w+)\s+only\b", value)
            if match:
                excluded, included = match.groups()
                word = excluded or included
                return f"scope:{word}", "excluded" if excluded else "included"
        return None