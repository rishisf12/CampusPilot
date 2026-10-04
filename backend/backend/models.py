"""SQLModel tables for ClassPilot."""
from datetime import date, time, datetime
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


class User(SQLModel, table=True):
    __tablename__ = "user"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    full_name: Optional[str] = None
    username: str = Field(index=True, unique=True)
    roll_number: Optional[str] = Field(default=None, index=True)
    is_email_verified: bool = Field(default=False)
    created_at: datetime = Field(default=None)
    updated_at: datetime = Field(default=None)

    profile: Optional["UserProfile"] = Relationship(back_populates="user")


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", unique=True, index=True)
    
    # Basic info
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    programme: Optional[str] = None
    semester: int = 1
    branch: str = "CSE A"
    section: Optional[str] = None
    
    # Electives and attendance
    elective_codes: List[str] = Field(default=[], sa_column=Column(JSON))
    attendance_target: float = Field(default=75.0)
    
    # Branch change history
    original_branch: Optional[str] = None
    branch_changed_at: Optional[datetime] = None
    
    # Branch change request
    branch_change_requested: bool = False
    requested_branch: Optional[str] = None
    branch_change_reason: Optional[str] = None
    branch_change_requested_at: Optional[datetime] = None
    
    user: Optional[User] = Relationship(back_populates="profile")


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