"""CLI entry point for timetable processing pipeline.

Usage:
    python -m app.features.timetable.cli process input/timetable_latest.pdf
    python -m app.features.timetable.cli diff old.xlsx new.xlsx
    python -m app.features.timetable.cli export --format excel
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure backend/ is on sys.path when run as module
# cli.py is at backend/app/features/timetable/cli.py -> parents[2] = backend/
_backend_dir = Path(__file__).resolve().parents[2]
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.features.timetable.config import get_config
from app.features.timetable.parser import parse_timetable_file
from app.features.timetable.excel_export import export_timetable_to_excel
from app.features.timetable.sql_seeder import export_timetable_to_sql
from app.features.timetable.diff import diff_timetables, format_diff_report
from app.features.timetable.notifier import get_notifier
from app.models import TimetableSlot

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def cmd_process(args):
    """Process a timetable PDF through the full pipeline."""
    config = get_config()
    pdf_path = Path(args.pdf_path)
    
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    
    print(f"Processing: {pdf_path}")
    print(f"Config: {config.source.get('semester_label', 'Unknown')}")
    print()
    
    # Parse
    print("Step 1: Parsing PDF...")
    result = parse_timetable_file(pdf_path, is_csv=False)
    slots = result["slots"]
    warnings = result.get("warnings", [])
    
    if not slots:
        print("ERROR: No slots found in PDF", file=sys.stderr)
        if warnings:
            print(f"First warning: {warnings[0]}", file=sys.stderr)
        return 1
    
    print(f"  Parsed {len(slots)} slots")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
        for w in warnings[:5]:
            print(f"    - {w}")
    
    # Convert dicts to TimetableSlot objects
    slot_objects = []
    for s in slots:
        slot_objects.append(TimetableSlot(
            day=s["day"],
            start_time=s["start_time"],
            end_time=s["end_time"],
            room=s.get("room", ""),
            course_code=s["course_code"],
            instructor=s.get("instructor"),
            branch_or_program=s["branch_or_program"],
            semester=s["semester"],
            remarks=s.get("remarks"),
        ))
    slots = slot_objects
    
    # Export Excel
    print("\nStep 2: Generating Excel...")
    output_dir = Path(config.output.get("output_dir", "output/"))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    excel_path = output_dir / config.get_output_filename("excel")
    export_result = export_timetable_to_excel(slots, excel_path)
    print(f"  Excel: {export_result['path']}")
    print(f"  Sheets: {', '.join(export_result['sheets'][:5])}...")
    
    # Export SQL
    print("\nStep 3: Generating SQL...")
    sql_path = output_dir / "timetable.sql"
    sql_result = export_timetable_to_sql(slots, sql_path)
    print(f"  SQL: {sql_result['path']}")
    
    # Save metadata
    metadata = {
        "version": config.source.get("version", "Unknown"),
        "effective_date": config.source.get("effective_date"),
        "slots_count": len(slots),
        "warnings": warnings,
        "outputs": {
            "excel": str(excel_path),
            "sql": str(sql_path),
        },
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\n  Metadata: {metadata_path}")
    
    # Notify
    if not args.no_notify:
        print("\nStep 4: Sending notifications...")
        notifier = get_notifier()
        asyncio.run(notifier.notify_success(
            slots_count=len(slots),
            version=config.source.get("version", "Unknown"),
            excel_path=str(excel_path),
            warnings=warnings,
        ))
    
    print("\n" + "=" * 50)
    print("Processing complete!")
    print(f"  Total slots: {len(slots)}")
    print(f"  Excel: {excel_path}")
    print(f"  SQL: {sql_path}")
    print("=" * 50)
    
    return 0


def cmd_diff(args):
    """Diff two timetable versions."""
    # Load slots from Excel files
    print("Diff functionality requires loading slots from Excel.")
    print("This will be implemented when needed.")
    return 0


def cmd_export(args):
    """Export current database timetable to specified format."""
    config = get_config()
    
    # This would load from database - for now, show help
    print(f"Export format: {args.format}")
    print(f"Output: {config.output.get('output_dir', 'output/')}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Timetable Processor CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Process command
    process_parser = subparsers.add_parser("process", help="Process a timetable PDF")
    process_parser.add_argument("pdf_path", help="Path to PDF file")
    process_parser.add_argument("--no-notify", action="store_true", help="Skip notifications")
    process_parser.set_defaults(func=cmd_process)
    
    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Diff two timetable versions")
    diff_parser.add_argument("old", help="Old version file")
    diff_parser.add_argument("new", help="New version file")
    diff_parser.set_defaults(func=cmd_diff)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export timetable")
    export_parser.add_argument("--format", choices=["excel", "json", "sql"], default="excel")
    export_parser.set_defaults(func=cmd_export)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())