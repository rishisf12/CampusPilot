"""Test script for timetable Excel export."""
import sys
from pathlib import Path

# Add backend to path (parents[2] from features/timetable/test.py -> backend/)
backend_path = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_path))

from datetime import time
from app.features.timetable.excel_export import TimetableExcelExporter, get_sheet_name, semester_to_roman, time_to_str


def test_semester_to_roman():
    """Test semester number to Roman numeral conversion."""
    assert semester_to_roman(1) == "I"
    assert semester_to_roman(3) == "III"
    assert semester_to_roman(5) == "V"
    assert semester_to_roman(7) == "VII"
    assert semester_to_roman(9) == "9"
    print("[PASS] semester_to_roman works correctly")


def test_get_sheet_name():
    """Test sheet name generation."""
    assert get_sheet_name(1, "CSE A") == "I-CSE-A"
    assert get_sheet_name(1, "CSE B") == "I-CSE-B"
    assert get_sheet_name(3, "ECE") == "III-ECE"
    assert get_sheet_name(5, "CSE A") == "V-CSE-A"
    assert get_sheet_name(7, "CSE") == "VII-CSE"
    assert get_sheet_name(9, "M.Tech (AI)") == "PG-MTech-AI"
    assert get_sheet_name(9, "Ph.D. (CSE)") == "PG-PhD-CSE"
    print("[PASS] get_sheet_name works correctly")


def test_time_to_str():
    """Test time formatting."""
    assert time_to_str(time(9, 0)) == "09:00-10:00"
    assert time_to_str(time(14, 30)) == "14:30-15:30"
    assert time_to_str(None) == ""
    print("[PASS] time_to_str works correctly")


def test_excel_generation():
    """Test full Excel generation with sample data."""
    from models import TimetableSlot
    
    # Create sample slots matching the PDF data
    sample_slots = [
        TimetableSlot(
            day="Mon",
            start_time=time(10, 0),
            end_time=time(10, 55),
            room="L102",
            course_code="NS1002",
            instructor="MKR",
            branch_or_program="CSE A",
            semester=1,
        ),
        TimetableSlot(
            day="Mon",
            start_time=time(11, 0),
            end_time=time(11, 55),
            room="L102",
            course_code="HS1001",
            instructor="JAMF",
            branch_or_program="CSE A",
            semester=1,
        ),
        TimetableSlot(
            day="Tue",
            start_time=time(8, 0),
            end_time=time(8, 55),
            room="Auditorium",
            course_code="ES1003",
            instructor="",
            branch_or_program="CSE A",
            semester=1,
        ),
        TimetableSlot(
            day="Mon",
            start_time=time(10, 0),
            end_time=time(10, 55),
            room="L202",
            course_code="NS1002",
            instructor="YSK",
            branch_or_program="CSE B",
            semester=1,
        ),
        TimetableSlot(
            day="Mon",
            start_time=time(9, 0),
            end_time=time(9, 55),
            room="L106",
            course_code="HS1001",
            instructor="MA",
            branch_or_program="ECE",
            semester=1,
        ),
        TimetableSlot(
            day="Mon",
            start_time=time(9, 0),
            end_time=time(9, 55),
            room="L105",
            course_code="CS8004",
            instructor="AO",
            branch_or_program="CSE",
            semester=7,
        ),
        TimetableSlot(
            day="Mon",
            start_time=time(11, 0),
            end_time=time(11, 55),
            room="CR102",
            course_code="EC5P01",
            instructor="PKP",
            branch_or_program="M.Tech (P&C)",
            semester=9,
        ),
    ]
    
    # Generate Excel
    output_path = Path(__file__).resolve().parents[1] / "output" / "test_timetable_export.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    exporter = TimetableExcelExporter(sample_slots)
    result = exporter.export(output_path)
    
    print(f"[PASS] Excel generated: {result['path']}")
    print(f"  Sheets: {result['sheets']}")
    print(f"  Total slots: {result['total_slots']}")
    
    # Verify file exists
    assert output_path.exists(), "Excel file was not created"
    assert output_path.stat().st_size > 0, "Excel file is empty"
    
    # Verify expected sheets exist
    expected_sheets = {"Index", "I-CSE-A", "I-CSE-B", "I-ECE", "VII-CSE", "PG-MTech-PC", "All Entries", "Check Items"}
    actual_sheets = set(result["sheets"])
    missing = expected_sheets - actual_sheets
    assert not missing, f"Missing sheets: {missing}"
    
    print("[PASS] All expected sheets present")
    print(f"\nTest complete! Excel file: {output_path}")


if __name__ == "__main__":
    print("Testing timetable Excel export...\n")
    
    test_semester_to_roman()
    test_get_sheet_name()
    test_time_to_str()
    test_excel_generation()
    
    print("\n" + "="*50)
    print("ALL TESTS PASSED!")
    print("="*50)