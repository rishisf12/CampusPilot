"""SQL seeder - generates INSERT statements from timetable slots."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import time

from app.models import TimetableSlot
from app.features.timetable.excel_export import time_to_str, semester_to_roman, get_sheet_name

logger = logging.getLogger(__name__)


class TimetableSQLSeeder:
    """Generates SQL INSERT statements for timetable slots."""
    
    def __init__(self, slots: List[TimetableSlot]):
        self.slots = slots
    
    def generate_sql(self) -> str:
        """Generate SQL INSERT statements."""
        lines = [
            "-- Timetable SQL Seeder",
            "-- Generated automatically from parsed timetable data",
            "",
            "DELETE FROM academic.timetable_slot;",
            "",
        ]
        
        for slot in self.slots:
            sql = self._generate_insert(slot)
            lines.append(sql)
        
        return "\n".join(lines)
    
    def _generate_insert(self, slot: TimetableSlot) -> str:
        """Generate a single INSERT statement."""
        start_time = slot.start_time.strftime("%H:%M") if slot.start_time else "NULL"
        end_time = slot.end_time.strftime("%H:%M") if slot.end_time else "NULL"
        
        # Escape single quotes in strings
        room = f"'{(slot.room or '').replace(chr(39), chr(39)+chr(39))}'" if slot.room else "NULL"
        course_code = f"'{slot.course_code.replace(chr(39), chr(39)+chr(39))}'"
        instructor = f"'{(slot.instructor or '').replace(chr(39), chr(39)+chr(39))}'" if slot.instructor else "NULL"
        branch = f"'{slot.branch_or_program.replace(chr(39), chr(39)+chr(39))}'"
        remarks = f"'{(slot.remarks or '').replace(chr(39), chr(39)+chr(39))}'" if slot.remarks else "NULL"
        
        return (
            f"INSERT INTO academic.timetable_slot "
            f"(day, start_time, end_time, room, course_code, instructor, branch_or_program, semester, remarks) "
            f"VALUES ('{slot.day}', '{start_time}', '{end_time}', {room}, {course_code}, "
            f"{instructor}, {branch}, {slot.semester}, {remarks});"
        )
    
    def export(self, output_path: Path) -> Dict[str, Any]:
        """Export SQL to file."""
        sql = self.generate_sql()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(sql, encoding="utf-8")
        logger.info(f"SQL exported to {output_path}")
        
        return {
            "path": str(output_path),
            "total_slots": len(self.slots),
        }


def export_timetable_to_sql(slots: List[TimetableSlot], output_path: Path) -> Dict[str, Any]:
    """Convenience function to export timetable to SQL."""
    seeder = TimetableSQLSeeder(slots)
    return seeder.export(output_path)