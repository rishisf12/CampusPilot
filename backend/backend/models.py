"""SQLModel tables for ClassPilot."""
from datetime import date, time
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    CANCELLED = "Cancelled"


class Course(SQLModel, table=True):
    __tablename__ = "course"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    semester: int
    branch: str
    is_elective: bool = False
    is_extra: bool = False

    attendance_records: List["AttendanceRecord"] = Relationship(back_populates="course")


class AttendanceRecord(SQLModel, table=True):
    __tablename__ = "attendance_record"
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    date: date
    status: AttendanceStatus

    course: Course = Relationship(back_populates="attendance_records")


class TimetableSlot(SQLModel, table=True):
    __tablename__ = "timetable_slot"
    id: Optional[int] = Field(default=None, primary_key=True)
    day: str = Field(index=True)  # Mon, Tue, ...
    start_time: time
    end_time: time
    room: str
    course_code: str = Field(index=True)
    branch_or_program: str
    semester: int


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"
    id: Optional[int] = Field(default=None, primary_key=True)
    semester: int
    branch: str
    elective_codes: List[str] = Field(default=[], sa_column=Column(JSON))


class ExamSeating(SQLModel, table=True):
    __tablename__ = "exam_seating"
    id: Optional[int] = Field(default=None, primary_key=True)
    roll_start_prefix: str = Field(index=True)
    roll_start_num: int = Field(index=True)
    roll_end_num: int = Field(index=True)
    room: str
    exam_date: date
    start_time: time
    end_time: time
    course_code: str