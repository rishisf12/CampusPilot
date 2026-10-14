"""Change detection - diff two timetable versions to highlight changes."""
import logging
from datetime import time
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from models import TimetableSlot

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class SlotChange:
    """Represents a change to a single slot."""
    change_type: ChangeType
    slot_key: str
    old_slot: Optional[TimetableSlot] = None
    new_slot: Optional[TimetableSlot] = None
    modified_fields: List[str] = field(default_factory=list)


@dataclass
class TimetableDiff:
    """Full diff between two timetable versions."""
    added: List[SlotChange] = field(default_factory=list)
    removed: List[SlotChange] = field(default_factory=list)
    modified: List[SlotChange] = field(default_factory=list)
    unchanged_count: int = 0
    
    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)
    
    @property
    def summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)} added")
        if self.removed:
            parts.append(f"-{len(self.removed)} removed")
        if self.modified:
            parts.append(f"~{len(self.modified)} modified")
        return ", ".join(parts) if parts else "No changes"


def _slot_key(slot: TimetableSlot) -> str:
    """Generate a unique key for a slot based on its identity."""
    return f"{slot.day}|{slot.start_time}|{slot.branch_or_program}|{slot.course_code}"


def _slots_equal(old: TimetableSlot, new: TimetableSlot) -> Tuple[bool, List[str]]:
    """Check if two slots are equal. Returns (is_equal, modified_fields)."""
    modified = []
    
    if old.day != new.day:
        modified.append("day")
    if old.start_time != new.start_time:
        modified.append("start_time")
    if old.end_time != new.end_time:
        modified.append("end_time")
    if old.room != new.room:
        modified.append("room")
    if old.course_code != new.course_code:
        modified.append("course_code")
    if old.instructor != new.instructor:
        modified.append("instructor")
    if old.branch_or_program != new.branch_or_program:
        modified.append("branch_or_program")
    if old.semester != new.semester:
        modified.append("semester")
    if old.remarks != new.remarks:
        modified.append("remarks")
    
    return (len(modified) == 0, modified)


def diff_timetables(
    old_slots: List[TimetableSlot],
    new_slots: List[TimetableSlot],
) -> TimetableDiff:
    """
    Compare two timetable versions and return a diff.
    
    Slots are matched by (day, start_time, branch, course_code).
    """
    old_map: Dict[str, TimetableSlot] = {}
    new_map: Dict[str, TimetableSlot] = {}
    
    for slot in old_slots:
        key = _slot_key(slot)
        old_map[key] = slot
    
    for slot in new_slots:
        key = _slot_key(slot)
        new_map[key] = slot
    
    result = TimetableDiff()
    
    # Find added and modified slots
    for key, new_slot in new_map.items():
        if key not in old_map:
            result.added.append(SlotChange(
                change_type=ChangeType.ADDED,
                slot_key=key,
                new_slot=new_slot,
            ))
        else:
            old_slot = old_map[key]
            is_equal, modified_fields = _slots_equal(old_slot, new_slot)
            if not is_equal:
                result.modified.append(SlotChange(
                    change_type=ChangeType.MODIFIED,
                    slot_key=key,
                    old_slot=old_slot,
                    new_slot=new_slot,
                    modified_fields=modified_fields,
                ))
            else:
                result.unchanged_count += 1
    
    # Find removed slots
    for key, old_slot in old_map.items():
        if key not in new_map:
            result.removed.append(SlotChange(
                change_type=ChangeType.REMOVED,
                slot_key=key,
                old_slot=old_slot,
            ))
    
    logger.info(f"Diff complete: {result.summary}")
    return result


def format_diff_report(diff: TimetableDiff) -> str:
    """Format a diff as a human-readable report."""
    lines = [
        "=" * 60,
        "TIMETABLE CHANGE REPORT",
        "=" * 60,
        f"Summary: {diff.summary}",
        f"Unchanged: {diff.unchanged_count}",
        "",
    ]
    
    if diff.added:
        lines.append(f"--- ADDED ({len(diff.added)}) ---")
        for change in diff.added:
            slot = change.new_slot
            lines.append(
                f"  + {slot.day} {slot.start_time} | {slot.branch_or_program} | "
                f"{slot.course_code} | {slot.room} | {slot.instructor or 'TBA'}"
            )
        lines.append("")
    
    if diff.removed:
        lines.append(f"--- REMOVED ({len(diff.removed)}) ---")
        for change in diff.removed:
            slot = change.old_slot
            lines.append(
                f"  - {slot.day} {slot.start_time} | {slot.branch_or_program} | "
                f"{slot.course_code} | {slot.room} | {slot.instructor or 'TBA'}"
            )
        lines.append("")
    
    if diff.modified:
        lines.append(f"--- MODIFIED ({len(diff.modified)}) ---")
        for change in diff.modified:
            old = change.old_slot
            new = change.new_slot
            lines.append(f"  ~ {new.day} {new.start_time} | {new.branch_or_program} | {new.course_code}")
            for field_name in change.modified_fields:
                old_val = getattr(old, field_name, "")
                new_val = getattr(new, field_name, "")
                lines.append(f"      {field_name}: '{old_val}' -> '{new_val}'")
        lines.append("")
    
    return "\n".join(lines)