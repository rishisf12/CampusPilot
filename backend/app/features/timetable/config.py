"""Configuration loader for timetable processor."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "timetable_config.yaml"


class TimetableConfig:
    """Loads and provides access to timetable configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with self.config_path.open("r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)
        
        logger.info(f"Loaded timetable config from {self.config_path}")
    
    @property
    def source(self) -> Dict[str, Any]:
        return self._config.get("source", {})
    
    @property
    def parsing(self) -> Dict[str, Any]:
        return self._config.get("parsing", {})
    
    @property
    def time_slots(self) -> list:
        return self.parsing.get("time_slots", [])
    
    @property
    def semesters(self) -> list:
        return self.parsing.get("semesters", [])
    
    @property
    def branches(self) -> Dict[str, list]:
        return self._config.get("branches", {})
    
    @property
    def instructors(self) -> Dict[str, str]:
        return self._config.get("instructors", {})
    
    @property
    def rooms(self) -> Dict[str, str]:
        return self._config.get("rooms", {})

    @property
    def output(self) -> Dict[str, Any]:
        return self._config.get("output", {})
    
    @property
    def validation(self) -> Dict[str, Any]:
        return self._config.get("validation", {})
    
    def get_branch_config(self, semester: str) -> list:
        """Get branch configuration for a semester."""
        return self.branches.get(semester, [])
    
    def get_instructor_name(self, initials: str) -> str:
        """Get full name for instructor initials."""
        return self.instructors.get(initials, initials)
    
    def get_room_description(self, room_code: str) -> str:
        """Get description for a room code prefix."""
        # Extract prefix (letters before digits)
        import re
        match = re.match(r"^([A-Z]+)", room_code.upper())
        if match:
            prefix = match.group(1)
            return self.rooms.get(prefix, room_code)
        return room_code
    
    def get_output_filename(self, format_type: str) -> str:
        """Get output filename for a format type."""
        if format_type == "excel":
            return self.output.get("excel_filename", "timetable.xlsx")
        elif format_type == "json":
            return self.output.get("json_filename", "timetable.json")
        return f"timetable.{format_type}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Return full config as dictionary."""
        return self._config


# Global config instance
_config_instance: Optional[TimetableConfig] = None


def get_config(config_path: Optional[Path] = None) -> TimetableConfig:
    """Get or create global config instance."""
    global _config_instance
    if _config_instance is None or config_path is not None:
        _config_instance = TimetableConfig(config_path)
    return _config_instance


def reload_config(config_path: Optional[Path] = None) -> TimetableConfig:
    """Force reload config from file."""
    global _config_instance
    _config_instance = TimetableConfig(config_path)
    return _config_instance