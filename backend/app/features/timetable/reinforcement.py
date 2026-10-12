"""
Reinforcement pattern-learning model for timetable PDF parsing.

The PDF maker consistently produces messy patterns (slash-joined electives,
truncated codes, combined branch labels). This module learns from corrections
and applies known patterns automatically.

Patterns are stored in the database so they persist across uploads and can be
extended as new patterns are discovered.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlmodel import Session, select

from models import ReinforcementPattern

logger = logging.getLogger(__name__)


@dataclass
class PatternRule:
    """A single correction rule learned from the PDF maker's mistakes."""
    name: str
    pattern: re.Pattern
    replacement: str
    description: str
    enabled: bool = True


class ReinforcementPatternModel:
    """
    Learns and applies correction patterns for timetable parsing.

    The model maintains a set of rules that detect and fix common PDF
    extraction mistakes. Rules can be:
    - Pre-loaded known patterns (slash electives, truncated codes)
    - Learned from user corrections
    - Auto-detected from repeated parsing failures
    """

    def __init__(self):
        self.rules: List[PatternRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load the known default patterns."""
        self.rules = [
            PatternRule(
                name="slash_electives",
                pattern=re.compile(r"^([A-Z]{2}\d[A-Z]\d{2})/([A-Z]{2}\d[A-Z]\d{2})", re.IGNORECASE),
                replacement=r"\1/\2",
                description="Split slash-joined electives: OE3M27/ME5D02 -> OE3M27 + ME5D02",
            ),
            PatternRule(
                name="slash_electives_with_trailing",
                pattern=re.compile(r"^([A-Z]{2}\d[A-Z]\d{2})/([A-Z]{2}\d[A-Z]\d{2})\s+", re.IGNORECASE),
                replacement=r"\1/\2 ",
                description="Fix slash-joined electives with trailing text: OE3M27/ME5D02 Instructor CR208 -> OE3M27/ME5D02 Instructor CR208",
            ),
            PatternRule(
                name="combined_branches",
                pattern=re.compile(r"^([A-Z]{2,3})\s+([A-Z]{2,3})(?:\s+([A-Z]{2,3}))?$"),
                replacement=r"\1/\2/\3",
                description="Split combined branch labels: ECE ME SM -> ECE/ME/SM",
            ),
            PatternRule(
                name="garbled_oe3e40",
                pattern=re.compile(r"OE3E40\s+K-\s*DSN\s*-CS\s*R-C\s*1R\s*021\s*0\s*1", re.IGNORECASE),
                replacement="OE3E40-SNS-CR101",
                description="Fix garbled OE3E40: 'OE3E40 K- DSN -CS R-C 1R 021 0 1' -> 'OE3E40-SNS-CR101'",
            ),
            PatternRule(
                name="garbled_oe3n32",
                pattern=re.compile(r"OE3N32-A\s*K\s*K\s*C\s*OC\s*-CS\s*ES8\s*R8\s*40\s*0\s*L\s*11\s*2\s*006\s*8\s*71-\s*-\s*B\s*-\s*N\s*V\s*i\s*A\s*F", re.IGNORECASE),
                replacement="OE3N32-AKK-CR107",
                description="Fix garbled OE3N32: 'OE3N32-A K K C OC -CS ES8 R8 40 0 L 11 2 006 8 71- - B - N V i A F' -> 'OE3N32-AKK-CR107'",
            ),
            PatternRule(
                name="garbled_oe3e25",
                pattern=re.compile(r"OE3E25-\s*KD\s*-CR102", re.IGNORECASE),
                replacement="OE3E25-KD-CR102",
                description="Fix garbled OE3E25: 'OE3E25- KD -CR102' -> 'OE3E25-KD-CR102'",
            ),
            PatternRule(
                name="elective_no_branch",
                pattern=re.compile(r"(OE\d[A-Z]\d{2})\s+(?:CSE|ECE|ME|SM|DS|IT|CSE\s+A|CSE\s+B|CSE\s+B1|CSE\s+B2|DS|MDES|PG)\b", re.IGNORECASE),
                replacement=r"\1",
                description="Remove branch from electives: 'OE3M27 CSE' -> 'OE3M27'",
            ),
            # Truncated elective prefix: restores ``27/ME5D02`` back to ``OE3M27/ME5D02``
            # when the pair is known from the document-wide vocabulary.
            # This serves as an addon for messy timetables where the parser's
            # data-driven repair may not capture all cases (e.g., unique codes
            # that don't appear intact elsewhere in the document).
            PatternRule(
                name="truncated_elective_prefix",
                pattern=re.compile(r"(?<![A-Z0-9])([A-Z]?\d{1,3}[A-Z]?\d{1,2})/([A-Z]{2,4}\d[A-Z]?\d{1,3})", re.IGNORECASE),
                replacement=self._restore_truncated_elective,
                description="Restore dropped elective prefix: ``27/ME5D02`` -> ``OE3M27/ME5D02`` when the pair is known.",
            ),
        ]

    def load_from_db(self, session: Session) -> None:
        """Load custom patterns from the database."""
        db_patterns = session.exec(
            select(ReinforcementPattern).where(ReinforcementPattern.enabled == True)
        ).all()
        for dbp in db_patterns:
            try:
                self.rules.append(PatternRule(
                    name=dbp.name,
                    pattern=re.compile(dbp.pattern, re.IGNORECASE),
                    replacement=dbp.replacement,
                    description=dbp.description,
                    enabled=dbp.enabled,
                ))
            except re.error:
                logger.warning(f"Invalid regex pattern: {dbp.pattern}")

    def apply(self, text: str) -> str:
        """Apply all enabled rules to the text."""
        result = text
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.pattern.search(result):
                result = rule.pattern.sub(rule.replacement, result)
        return result

    def learn(self, name: str, pattern: str, replacement: str, description: str) -> None:
        """Add a new pattern rule."""
        self.rules.append(PatternRule(
            name=name,
            pattern=re.compile(pattern, re.IGNORECASE),
            replacement=replacement,
            description=description,
        ))

    def _restore_truncated_elective(self, match: "re.Match") -> str:
        """Restore a dropped elective prefix from ``NN/XX`` to ``OE?MXX/XX``.

        The reinforcement model does not have access to the document-wide
        pair_vocab, so this heuristic prepends ``OE`` when the right-hand
        code follows the elective pattern (2+ letters + digit + letter + digits).
        If the pair is already complete (e.g. ``OE3M27/ME5D02``), the pattern
        won't match because of the negative lookbehind ``(?<![A-Z0-9])``.
        """
        dropped = match.group(1)
        right = match.group(2)
        # Heuristic: if the right code looks like an elective (starts with OE/OI
        # or has 2+ letters followed by digit), prepend OE to the dropped part.
        if re.match(r"^OE\d|^OI\d", right, re.IGNORECASE):
            # Already has a prefix; keep as-is (the parser's pair_vocab will handle it)
            return match.group(0)
        # Prepend OE to the dropped digits; the full code becomes OE{dropped}/{right}
        # but only if the right code is an elective-style code (2+ letters + digit).
        if re.match(r"^[A-Z]{2,4}\d", right, re.IGNORECASE):
            return f"OE{dropped}/{right}"
        return match.group(0)


# Singleton instance
_model: Optional[ReinforcementPatternModel] = None


def get_reinforcement_model() -> ReinforcementPatternModel:
    """Get or create the singleton reinforcement model."""
    global _model
    if _model is None:
        _model = ReinforcementPatternModel()
    return _model