"""SQLModel tables for ClassPilot."""
from datetime import date, time, datetime
from typing import Any, Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa
from sqlalchemy import BigInteger, Date, DateTime, Identity, Text, UniqueConstraint, func, Enum as SAEnum, Integer, ForeignKey
from enum import Enum


def normalize_tags(values: Optional[List[str]]) -> List[str]:
    """Lowercase + trim each tag, drop empties, dedupe. 'React ' == 'react'."""
    cleaned: List[str] = []
    for value in values or []:
        tag = str(value).strip().lower()
        if tag and tag not in cleaned:
            cleaned.append(tag)
    return cleaned


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    CANCELLED = "Cancelled"


class UserRole(str, Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    ADMIN = "admin"


class JoinRequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ExamUploadKind(str, Enum):
    TIMETABLE = "timetable"
    SEATING = "seating"


class PurchaseKind(str, Enum):
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"
    CONSUMABLE = "consumable"
    RESTORE = "restore"


class CrashReportKind(str, Enum):
    CRASH = "crash"
    ANR = "anr"


class SecurityEventKind(str, Enum):
    FAILED_LOGIN = "failed_login"
    BRUTE_FORCE = "brute_force"
    TOKEN_MISUSE = "token_misuse"
    API_ABUSE = "api_abuse"
    ROOT_DETECTED = "root_detected"
    EMULATOR_DETECTED = "emulator_detected"
    TAMPER_DETECTED = "tamper_detected"
    RATE_LIMITED = "rate_limited"
    WAF_BLOCKED = "waf_blocked"


class ScanResultStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class HackathonSource(str, Enum):
    EMAIL = "email"
    MANUAL = "manual"


class Course(SQLModel, table=True):
    __tablename__ = "course"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    instructor: Optional[str] = None
    is_elective: bool = False
    is_extra: bool = False

    attendance_records: List["AttendanceRecord"] = Relationship(back_populates="course")
    offerings: List["CourseOffering"] = Relationship(back_populates="course")


class Branch(SQLModel, table=True):
    """Academic branch/department lookup table."""
    __tablename__ = "branch"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)  # CSE, ECE, ME, etc.
    name: str
    programme: Optional[str] = None  # BTech, MTech, BDes, etc.
    is_active: bool = Field(default=True)


class AcademicTerm(SQLModel, table=True):
    """Academic term (e.g. 2025-26 Sem 1)."""

    __tablename__ = "academic_term"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    academic_year: str
    term_number: int = 1
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    is_current: bool = Field(default=False)


class CourseOffering(SQLModel, table=True):
    """A course as offered in a specific term to a specific branch."""
    __tablename__ = "course_offering"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(Integer, ForeignKey("academic.course.id", ondelete="CASCADE"), index=True))
    term_id: int = Field(sa_column=Column(Integer, ForeignKey("academic.academic_term.id", ondelete="CASCADE"), index=True))
    branch_id: int = Field(sa_column=Column(Integer, ForeignKey("academic.branch.id", ondelete="CASCADE"), index=True))
    semester: int
    section: Optional[str] = Field(default=None, index=True)
    instructor: Optional[str] = None

    course: Course = Relationship(back_populates="offerings")


class TimetableSlotBranch(SQLModel, table=True):
    """Junction table: a timetable slot can be attended by multiple branches."""
    __tablename__ = "timetable_slot_branch"
    __table_args__ = (
        UniqueConstraint("slot_id", "branch_id", name="uq_timetable_slot_branch"),
        {"schema": "academic"},
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    slot_id: int = Field(foreign_key="academic.timetable_slot.id", index=True)
    branch_id: int = Field(foreign_key="academic.branch.id", index=True)


class AttendanceRecord(SQLModel, table=True):
    __tablename__ = "attendance_record"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "date", name="uq_attendance_user_course_date"),
        {"schema": "academic"},
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.user.id", index=True)
    course_id: int = Field(foreign_key="academic.course.id", index=True)
    date: date
    status: AttendanceStatus = Field(sa_column=Column("status", SAEnum(AttendanceStatus, native_enum=False, values_callable=lambda x: [e.value for e in x])))

    course: Course = Relationship(back_populates="attendance_records")
    user: "User" = Relationship(back_populates="attendance_records")


class TimetableSlot(SQLModel, table=True):
    __tablename__ = "timetable_slot"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    day: str = Field(index=True)  # Mon, Tue, ...
    start_time: time
    end_time: time
    room: str
    course_code: str = Field(index=True)
    #: Faculty initials or short name, when the source lists one.
    instructor: Optional[str] = Field(default=None)
    branch_or_program: str
    semester: Optional[int] = Field(default=None, index=True)
    offering_id: Optional[int] = Field(
        default=None,
        foreign_key="academic.course_offering.id",
    )
    #: Who uploaded the row. ``None`` is an admin upload - the public index
    #: every account reads. A user id is an individual's own upload, shown in
    #: their account only.
    uploaded_by: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)


class ReinforcementPattern(SQLModel, table=True):
    __tablename__ = "reinforcement_pattern"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    pattern: str
    replacement: str
    description: str
    enabled: bool = Field(default=True)
    created_at: Optional[str] = Field(default=None)


class User(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    full_name: Optional[str] = None
    username: str = Field(index=True, unique=True)
    roll_number: Optional[str] = Field(default=None, index=True)
    is_email_verified: bool = Field(default=False)
    #: ``"student"`` or ``"admin"``. New accounts are students; the developer
    #: promotes an account with ``tools/make_admin.py``. Student signup never
    #: sets this, so it cannot be self-granted.
    role: UserRole = Field(
        default=UserRole.STUDENT,
        sa_column=Column("role", SAEnum(UserRole, name="user_role", native_enum=True, values_callable=lambda x: [e.value for e in x]), nullable=False, default="student", index=True)
    )
    #:
    #: When the password last changed. A reset stamps this, and any session token
    #: issued before it is refused - otherwise a stolen password stays useful for
    #: the full 7-day token life even after the owner resets it.
    #:
    #: Tokens issued before this column existed carry no stamp, which reads as
    #: "older than any reset" and so is rejected. That is the safe direction.
    password_changed_at: Optional[datetime] = Field(
        default=None, sa_column=Column("password_changed_at", DateTime, nullable=True)
    )
    #: Account standing, written by the admin suspend/ban actions. Checked at
    #: login: a suspended or banned account gets 403 even with the right
    #: password. `suspended_until` lets a suspension lapse on its own; NULL
    #: means indefinite. Without these columns the suspend/ban buttons recorded
    #: a log row and changed nothing - the assignment raised ValueError because
    #: the fields did not exist.
    is_suspended: bool = Field(default=False)
    suspended_until: Optional[datetime] = Field(
        default=None, sa_column=Column("suspended_until", DateTime, nullable=True)
    )
    is_banned: bool = Field(default=False)
    #: Server-side defaults: SQLModel 0.0.22 cannot use `default_factory` under
    #: Pydantic 2.10, so the timestamp is filled by the database instead.
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column("updated_at", DateTime, nullable=False, server_default=func.now()),
    )

    attendance_records: List["AttendanceRecord"] = Relationship(back_populates="user")


class PendingSignup(SQLModel, table=True):
    """
    An address being verified *before* any account exists for it.

    The old flow created the account first and verified afterwards, which left a
    half-built account behind whenever someone mistyped the code or gave up. Here
    nothing is created until the address is proven, so an abandoned signup leaves
    only a row that expires.

    The code is stored hashed and the address is the salt - there is no user id
    yet to salt with, and the email is the thing being proven anyway.
    """

    __tablename__ = "pending_signup"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    #: Lower-cased, so a mixed-case request finds the same row.
    email: str = Field(index=True, unique=True)
    code_hash: str
    #: Wrong guesses so far. At the limit the code is dead, not merely blocked.
    attempts: int = 0
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )
    #: Set once the correct code is entered. This is the gate on account creation.
    verified_at: Optional[datetime] = Field(
        default=None, sa_column=Column("verified_at", DateTime, nullable=True)
    )


class PasswordResetCode(SQLModel, table=True):
    """
    A one-time code emailed to the account's *registered* address.

    Stored in the database rather than in memory so a restart cannot lose a code
    a student is already holding, and so a second worker still sees it. The code
    is stored hashed, never in the clear: this table sits on disk.

    ``attempts`` is the real protection against guessing a six-digit code - the
    hash is fast, so without a counter a database copy would be enumerable.
    """

    __tablename__ = "password_reset_code"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(index=True, foreign_key="core.user.id")
    #: SHA-256 of the six-digit code.
    code_hash: str = Field(index=True)
    #: Wrong guesses so far. At the limit the code is dead, not merely blocked.
    attempts: int = 0
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )
    used_at: Optional[datetime] = Field(
        default=None, sa_column=Column("used_at", DateTime, nullable=True)
    )


class PasskeyCredential(SQLModel, table=True):
    """
    A passkey enrolled by a user.

    Only the *public* half of the credential is stored. The private key never
    leaves the device - it lives in Windows Hello, Touch ID, Android or a
    password manager - so this row cannot be used to impersonate the user, only to
    verify assertions that the device actually produced.
    """

    __tablename__ = "passkey_credential"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    #: Base64url credential id issued by the authenticator.
    credential_id: str = Field(index=True, unique=True)
    #: Base64url COSE public key, verified against the relying party on sign-up.
    public_key: str
    #: Monotonic counter used to spot a cloned authenticator.
    sign_count: int = 0
    #: Hint for the browser: how the device can be contacted.
    transports: List[str] = Field(default=[], sa_column=Column(JSON))
    #: Student-facing name, e.g. "Windows Hello" or "Phone".
    label: Optional[str] = None
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )
    last_used_at: Optional[datetime] = Field(default=None, sa_column=Column("last_used_at", DateTime, nullable=True))


class PasskeyChallenge(SQLModel, table=True):
    """
    A one-time WebAuthn challenge.

    Challenges must not be reusable and must not outlive their purpose, so they
    are stored rather than kept in memory: a restart, or a second worker, cannot
    silently accept a replayed challenge. ``purpose`` keeps a sign-up challenge
    from being spent on sign-in.
    """

    __tablename__ = "passkey_challenge"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    challenge: str = Field(index=True, unique=True)
    #: ``register`` or ``authenticate``. ``None`` for a discoverable sign-in.
    purpose: str
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", unique=True, index=True)
    
    # Basic info
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    #: Contact phone. Auto-filled into the feedback form so the student only
    #: types it once; kept on the profile (the single source of truth) rather
    #: than re-asked on every feedback.
    phone: Optional[str] = None
    programme: Optional[str] = None
    semester: int = 1
    #: The year the student joined, e.g. 2024 - the batch they belong to.
    #: The roll number's prefix carries it ("24BCS125" -> 2024), and it is
    #: what tells one batch's papers from another's, so the exam index can
    #: speak about the right students.
    batch_year: Optional[int] = None
    #: The teaching staff. A member of the faculty is not a student, so this
    #: flag is what tells the two apart when the admin asks "who are the
    #: faculty": the role column alone cannot, because an account only ever
    #: carries "admin" or "student".
    is_faculty: bool = False
    #: Faculty only: where they sit on the rolls - Professor, Associate
    #: Professor or Assistant Professor. Students have none.
    designation: Optional[str] = None
    #: Faculty only: the exact name notation this member appears under in the
    #: published timetable, e.g. "ARR". Students have none.
    timetable_notation: Optional[str] = None
    #: A class representative: a student who represents their class. The
    #: class is the batch, the branch and the semester, so those are what the
    #: admin filters on to find the CRs of a class.
    is_class_representative: bool = False
    #: Branch as free text. The academic-core normalisation added the
    #: ``branch_id`` FK below, but the profile, teams and branch-change flows
    #: still read and write the string form, so it is kept alongside the id.
    branch: Optional[str] = None
    branch_id: Optional[int] = Field(default=None, foreign_key="academic.branch.id", index=True)
    section: Optional[str] = None  # Section name (A, B, etc.)
    
    # Electives and attendance
    elective_codes: List[str] = Field(default=[], sa_column=Column(JSON))
    attendance_target: float = Field(default=75.0)

    # Team-finding (My Team): free-form skill tags, lowercased on write.
    skills: List[str] = Field(default=[], sa_column=Column(JSON))
    bio: Optional[str] = None
    contact: Optional[str] = None
    
    # Branch change history
    original_branch: Optional[str] = None
    original_branch_id: Optional[int] = Field(default=None, foreign_key="academic.branch.id")
    branch_changed_at: Optional[datetime] = None
    
    # Branch change request
    branch_change_requested: bool = False
    requested_branch: Optional[str] = None
    requested_branch_id: Optional[int] = Field(default=None, foreign_key="academic.branch.id")
    branch_change_reason: Optional[str] = None
    branch_change_requested_at: Optional[datetime] = None


class ExamSeating(SQLModel, table=True):
    """Seating index row: a continuous roll range mapped to one exam slot."""

    __tablename__ = "exam_seating"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    roll_start_prefix: str = Field(index=True)
    roll_start_num: int = Field(index=True)
    roll_end_num: int = Field(index=True)
    room: str
    #: `sa_column` avoids the collision with `datetime.date` in SA column naming.
    seating_date: Optional[date] = Field(default=None, sa_column=Column("seating_date", Date, nullable=True))
    start_time: time
    end_time: time
    course_code: str = Field(index=True)
    #: Branch the row belongs to (inferred from roll prefix or explicit PDF column).
    branch: Optional[str] = Field(default=None, index=True)
    semester: Optional[int] = Field(default=None, index=True)
    #: True for open-elective / extra-course rows that span other branches.
    is_extra: bool = Field(default=False, index=True)
    #: Who uploaded the row. ``None`` is an admin upload - the public index
    #: every account sees. A user id is an individual's own upload, shown in
    #: their account only.
    uploaded_by: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)


class ExamUpload(SQLModel, table=True):
    """
    The most recent source file uploaded for an exam section.

    Both the timetable and the seating index save under the same ``exam_``
    filename prefix, so the file on disk cannot be attributed to a section on
    its own.  This row records which section each upload belongs to, letting the
    UI offer "preview the PDF I uploaded here" instead of whichever file
    happened to be written last.
    """

    __tablename__ = "exam_upload"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    #: ``"timetable"`` or ``"seating"``. The Postgres enum stores the lowercase
    #: *values*, while ``SAEnum`` defaults to binding the uppercase member
    #: *names* - which the type rejects - so bind values explicitly.
    kind: ExamUploadKind = Field(
        sa_column=Column(
            "kind",
            SAEnum(ExamUploadKind, native_enum=False, values_callable=lambda x: [e.value for e in x]),
            index=True,
        )
    )
    #: Name of the file inside ``uploads/``.
    filename: str
    #: The name the user actually uploaded, shown in the UI.
    original_name: Optional[str] = Field(default=None)
    size_bytes: Optional[int] = Field(default=None)
    #: Set explicitly on insert; ``None`` for rows written by older code.
    uploaded_at: Optional[datetime] = Field(default=None, sa_column=Column("uploaded_at", DateTime, nullable=True))
    #: Who uploaded the file. ``None`` is an admin upload - its preview is
    #: public. A user id is an individual's upload, previewed in their account
    #: only.
    uploaded_by: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)


class TimetableUpload(SQLModel, table=True):
    """
    The most recent class-timetable file uploaded through the API.

    The uploads folder also collects CSV fixtures written by the test suite, so
    "newest file on disk" is not a reliable answer. Recording the upload here
    means the preview button can only ever offer a file a user actually uploaded.
    """

    __tablename__ = "timetable_upload"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    #: Name of the file inside ``uploads/``.
    filename: str
    #: The name the user actually uploaded, shown in the UI.
    original_name: Optional[str] = Field(default=None)
    size_bytes: Optional[int] = Field(default=None)
    #: Set explicitly on insert; ``None`` for rows written by older code.
    uploaded_at: Optional[datetime] = Field(default=None, sa_column=Column("uploaded_at", DateTime, nullable=True))
    #: Who uploaded the file. ``None`` is an admin upload - its preview is
    #: public. A user id is an individual's upload, previewed in their account
    #: only.
    uploaded_by: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    #: The academic term the upload belongs to. Added by the
    #: academic-core migration and used to group uploads by term;
    #: the model had fallen behind the database, which still
    #: carries the column and its rows.
    term_id: Optional[int] = Field(default=None, foreign_key="academic.academic_term.id", index=True)


class MidSemSchedule(SQLModel, table=True):
    """Mid-sem examination timetable row (branch + course + slot)."""

    __tablename__ = "mid_sem_schedule"
    __table_args__ = {"schema": "academic"}
    id: Optional[int] = Field(default=None, primary_key=True)
    #: `sa_column` avoids the collision with `datetime.date` in SA column naming.
    schedule_date: Optional[date] = Field(default=None, sa_column=Column("schedule_date", Date, nullable=True))
    start_time: time
    end_time: time
    course_code: str = Field(index=True)
    room: str
    branch: Optional[str] = Field(default=None, index=True)
    semester: Optional[int] = Field(default=None, index=True)
    #: OE group / elective group label when the PDF groups open electives.
    group: Optional[str] = Field(default=None)
    #: Who uploaded the row. ``None`` is an admin upload - the paper list every
    #: account reads. A user id is an individual's own upload, shown in their
    #: account only.
    uploaded_by: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)


class Feedback(SQLModel, table=True):
    """
    One feedback submission from a student.

    Name, phone and email are snapshotted at submit time from the profile and
    the account, so the admin "feedback responses" view always shows who wrote
    what even if the student later edits their profile. The attachment lives on
    disk under ``uploads/``; only its filename is stored here.
    """

    __tablename__ = "feedback"
    __table_args__ = {"schema": "social"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    #: Snapshot of who submitted: name + phone from the profile, email from the account.
    name: str = ""
    phone: Optional[str] = Field(default=None)
    email: str = ""
    #: Subject/title (from email subject or web form).
    subject: Optional[str] = Field(default=None)
    message: str = ""
    #: Stored filename inside ``uploads/`` (``feedback_<timestamp>_<uuid>.<ext>``).
    attachment_filename: Optional[str] = Field(default=None)
    #: The name the student actually uploaded, shown in the admin view.
    attachment_original: Optional[str] = Field(default=None)
    attachment_size: Optional[int] = Field(default=None)
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )


class FeedbackReply(SQLModel, table=True):
    """
    An admin's response to one feedback submission.

    Shown at the bottom of the student's own feedback entry, so the reply
    appears where the feedback was written rather than in a separate inbox.
    """

    __tablename__ = "feedback_reply"
    __table_args__ = {"schema": "social"}
    id: Optional[int] = Field(default=None, primary_key=True)
    feedback_id: int = Field(foreign_key="social.feedback.id", index=True)
    admin_user_id: Optional[int] = Field(default=None, foreign_key="core.user.id")
    message: str = ""
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )


class Team(SQLModel, table=True):
    """A hackathon team: what it builds, what it still needs, who owns it."""

    __tablename__ = "team"
    __table_args__ = {"schema": "social"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = Field(default="")
    #: What the team wants to build with, e.g. ["react", "python", "ml"].
    tech_stack: List[str] = Field(default=[], sa_column=Column(JSON))
    #: Tech stack the team still needs. Optional, shown as "Missing".
    wanted: List[str] = Field(default=[], sa_column=Column(JSON))
    max_members: int = Field(default=4, ge=2, le=20)
    #: When False, joining creates a JoinRequest instead of adding a member.
    request_to_join: bool = Field(default=False)
    is_open: bool = Field(default=True)
    hackathon_id: Optional[int] = Field(default=None, foreign_key="social.hackathon.id", index=True)
    owner_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )


class TeamMember(SQLModel, table=True):
    __tablename__ = "team_member"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member"),
        {"schema": "social"},
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: Optional[int] = Field(default=None, foreign_key="social.team.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    is_admin: bool = Field(default=False)
    is_approved: bool = Field(default=True)
    joined_at: datetime = Field(
        default=None,
        sa_column=Column("joined_at", DateTime, nullable=False, server_default=func.now()),
    )


class JoinRequest(SQLModel, table=True):
    __tablename__ = "join_request"
    __table_args__ = {"schema": "social"}
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: Optional[int] = Field(default=None, foreign_key="social.team.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    #: pending | accepted | rejected. Bind the lowercase *value*: the Postgres
    #: enum stores values, while ``SAEnum`` defaults to the uppercase names.
    status: JoinRequestStatus = Field(
        default="pending",
        sa_column=Column(
            "status",
            SAEnum(JoinRequestStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
            index=True,
        ),
    )
    message: Optional[str] = None
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )
    responded_at: Optional[datetime] = Field(default=None)


class Hackathon(SQLModel, table=True):
    """A hackathon event, or a feed entry mailed to the feed address."""

    __tablename__ = "hackathon"
    __table_args__ = {"schema": "social"}
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: str = Field(default="")
    link: Optional[str] = None
    poster_url: Optional[str] = None
    #: What entrants typically need - shown to a student choosing an event.
    tech_stack: List[str] = Field(default=[], sa_column=Column(JSON))
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = Field(default=True, index=True)
    is_featured: bool = Field(default=False, index=True)
    created_by: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now()),
    )

    # ----------------------------------------------------- feed provenance
    #: "email" for anything pulled from the mailbox, "manual" for rows created
    #: through the API. Retention sweeps on both - it is about disk, not origin.
    #: Bind the lowercase *value*: the Postgres enum stores values, while
    #: ``SAEnum`` defaults to the uppercase names.
    source: HackathonSource = Field(
        default="manual",
        sa_column=Column(
            "source",
            SAEnum(HackathonSource, native_enum=False, values_callable=lambda x: [e.value for e in x]),
            index=True,
        ),
    )
    #: Address that sent it, so a student can tell who to ask questions of.
    sender: Optional[str] = None
    #: Plain text only. Raw HTML from a public mailbox is hostile input and is
    #: never stored or rendered - see `services/feed.py`.
    body_text: Optional[str] = None
    #: http(s) URLs lifted out of the body, vetted at import. Rendered as real
    #: anchors rather than inlined markup.
    links: List[str] = Field(default=[], sa_column=Column(JSON))
    #: Stored filenames under FEED_MEDIA_DIR, not original names. Never trust
    #: a filename off the wire for a filesystem path.
    attachments: List[str] = Field(default=[], sa_column=Column(JSON))
    #: Last processed IMAP UID, so a message that was opened in Gmail first is
    #: still picked up. Tracked per mailbox rather than via the \Seen flag.
    feed_uid: Optional[int] = Field(default=None, index=True)


class FeedCursor(SQLModel, table=True):
    """Where the mail importer got to. One row per mailbox."""

    __tablename__ = "feed_cursor"
    __table_args__ = {"schema": "telemetry"}
    id: Optional[int] = Field(default=None, primary_key=True)
    mailbox: str = Field(default="INBOX", unique=True, index=True)
    #: IMAP UIDVALIDITY. When the server reports a different value the mailbox
    #: has been rebuilt and our UIDs are meaningless, so the cursor resets.
    uidvalidity: Optional[int] = None
    last_uid: int = Field(default=0)
    updated_at: datetime = Field(
        default=None,
        sa_column=Column("updated_at", DateTime, nullable=False, server_default=func.now()),
    )


class AdminProfile(SQLModel, table=True):
    """The administrator's own profile.

    A student profile is a roll number, a branch and a set of electives.
    None of that describes an administrator, and none of it belongs on their
    screen. This one carries what an operator actually works with:

    - how they are addressed (display name, job title, team);
    - how the console behaves for them (theme, density, the monitoring
      subsection and window they land on, the panels they keep pinned);
    - where their alerts go (email, the channels, their quiet hours);
    - their own notes.

    It holds nothing about anybody else. The admin's view of *other*
    people lives in User 360, which is a different screen on purpose.
    """

    __tablename__ = "admin_profile"
    __table_args__ = {"schema": "core"}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(
        default=None, foreign_key="core.user.id", unique=True, index=True
    )

    # How they are addressed
    display_name: Optional[str] = Field(default=None, max_length=120)
    job_title: Optional[str] = Field(default=None, max_length=120)
    team: Optional[str] = Field(default=None, max_length=120)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    locale: str = Field(default="en-IN", max_length=16)

    # How the console behaves for them
    theme: str = Field(default="system", max_length=16)
    density: str = Field(default="comfortable", max_length=16)
    #: The monitoring subsection they land on.
    default_subsection: Optional[str] = Field(default=None, max_length=32)
    default_window_days: int = 7
    #: The admin panels they keep pinned, by id.
    pinned_panels: List[str] = Field(default=[], sa_column=Column(JSON))

    # Where their alerts go
    notify_email: Optional[str] = Field(default=None, max_length=255)
    #: The channels they want to be reached on: email, telegram, webhook.
    notify_channels: List[str] = Field(default=[], sa_column=Column(JSON))
    #: {"start": "22:00", "end": "07:00", "timezone": "Asia/Kolkata"}
    quiet_hours: dict = Field(default_factory=dict, sa_column=Column(JSON, default=dict))

    #: The operator's own private notes. Never shown to anybody else.
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default=None, sa_column=Column("created_at", DateTime, nullable=False, server_default=func.now())
    )
    updated_at: datetime = Field(
        default=None, sa_column=Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    )

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    actor_id: Optional[int] = Field(default=None, index=True)
    actor_email: Optional[str] = Field(default=None, max_length=255)
    actor_role: Optional[str] = Field(default=None, max_length=50)
    action: str = Field(max_length=100, index=True)
    target_type: Optional[str] = Field(default=None, max_length=100, index=True)
    target_id: Optional[str] = Field(default=None, max_length=100, index=True)
    before_json: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    after_json: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    ip_hash: Optional[str] = Field(default=None, max_length=64)
    user_agent_hash: Optional[str] = Field(default=None, max_length=64)
    request_id: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    )


class FeatureFlag(SQLModel, table=True):
    __tablename__ = "feature_flag"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, Identity(), primary_key=True))
    key: str = Field(max_length=100, unique=True, index=True)
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    enabled: bool = Field(default=False)
    rollout_percentage: int = Field(default=0)
    target_roles: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_user_ids: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_platforms: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_app_versions: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    created_by: Optional[int] = Field(default=None)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))


class FlagTarget(SQLModel, table=True):
    __tablename__ = "flag_target"
    __table_args__ = {"schema": "core", "extend_existing": True}


class ExtraEvent(SQLModel, table=True):
    """Faculty-added extra class or quiz, linked to a course."""
    __tablename__ = "extra_event"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    course_code: str = Field(index=True, max_length=32)
    label: str = Field(max_length=128)
    event_date: date = Field(default=None)
    time_slot: Optional[str] = Field(default=None, max_length=64)
    instructor_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(
        default=None,
        sa_column=Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    )
    expires_at: Optional[datetime] = Field(default=None)
    cancelled: bool = Field(default=False)

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, Identity(), primary_key=True))
    flag_id: int = Field(sa_column=Column(Integer, ForeignKey("core.feature_flag.id", ondelete="CASCADE"), nullable=False, index=True))
    attribute: str = Field(max_length=50)
    operator: str = Field(max_length=20)
    values: List[str] = Field(default=[], sa_column=Column(postgresql.JSONB(astext_type=str)))


class MaintenanceWindow(SQLModel, table=True):
    __tablename__ = "maintenance_window"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, Identity(), primary_key=True))
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    enabled: bool = Field(default=False)
    global_maintenance: bool = Field(default=False)
    target_features: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    message: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    allow_list_user_ids: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    bypass_roles: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    scheduled_start: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    scheduled_end: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    created_by: Optional[int] = Field(default=None)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))


class RemoteConfig(SQLModel, table=True):
    __tablename__ = "remote_config"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, Identity(), primary_key=True))
    key: str = Field(max_length=100, unique=True, index=True)
    value: Any = Field(sa_column=Column(postgresql.JSONB(astext_type=str)))
    value_type: str = Field(max_length=20, default="json")
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    schema_json: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    schema_version: int = Field(default=1)
    is_public: bool = Field(default=False)
    updated_by: Optional[int] = Field(default=None)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))


class RemoteConfigHistory(SQLModel, table=True):
    __tablename__ = "remote_config_history"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, Identity(), primary_key=True))
    config_key: str = Field(max_length=100, index=True)
    value: Any = Field(sa_column=Column(postgresql.JSONB(astext_type=str)))
    value_type: str = Field(max_length=20)
    schema_version: int = Field(default=1)
    changed_by: Optional[int] = Field(default=None)
    change_reason: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))


class SystemSetting(SQLModel, table=True):
    """Admin system settings as plain key/value rows.

    The Settings tab reads and writes arbitrary keys (rate limits, timeouts,
    store URLs...), so a dedicated column per setting would mean a migration
    per UI field. Values are JSON so booleans, numbers and strings all fit.
    Unknown keys are accepted rather than rejected: the UI owns the key list.
    """

    __tablename__ = "system_setting"
    __table_args__ = {"schema": "core", "extend_existing": True}

    key: str = Field(max_length=100, primary_key=True)
    value: Any = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    updated_by: Optional[int] = Field(default=None)
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
class UserControlAction(SQLModel, table=True):
    __tablename__ = "user_control_action"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    admin_id: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False, index=True))
    target_user_id: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False, index=True))
    action: str = Field(max_length=50)
    reason: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
class Broadcast(SQLModel, table=True):
    __tablename__ = "broadcast"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    title: str = Field(max_length=200)
    body: str = Field(sa_column=Column(postgresql.TEXT))
    channel: str = Field(max_length=20)  # in_app, push, email
    target_roles: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_user_ids: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_branches: Optional[List[str]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_semesters: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    target_segments: Optional[List[int]] = Field(default=None, sa_column=Column(postgresql.JSONB(astext_type=str)))
    scheduled_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    created_by: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class BroadcastDelivery(SQLModel, table=True):
    __tablename__ = "broadcast_delivery"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    broadcast_id: int = Field(sa_column=Column(BigInteger, ForeignKey("core.broadcast.id", ondelete="CASCADE"), nullable=False, index=True))
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("core.user.id"), nullable=False, index=True))
    channel: str = Field(max_length=20)
    status: str = Field(max_length=20)  # pending, sent, failed, read
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    read_at: Optional[datetime] = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True)))
    error_message: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
class ForceUpdateRule(SQLModel, table=True):
    __tablename__ = "force_update_rule"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    platform: str = Field(max_length=20, index=True)  # ios, android, web
    min_version: str = Field(max_length=20)  # minimum required version
    recommended_version: str = Field(max_length=20)  # recommended version
    store_url: str = Field(max_length=500)  # app store / play store URL
    message: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    is_active: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
class SecurityEvent(SQLModel, table=True):
    __tablename__ = "security_event"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    event_type: str = Field(max_length=50, index=True)  # failed_login, brute_force, new_admin, role_change, unusual_ip, rate_limit
    severity: str = Field(max_length=20)  # low, medium, high, critical
    actor_email: Optional[str] = Field(default=None, max_length=255)
    actor_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id"), index=True))
    details: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    ip_hash: Optional[str] = Field(default=None, max_length=64)
    user_agent_hash: Optional[str] = Field(default=None, max_length=64)
    request_id: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class SecurityFeed(SQLModel, table=True):
    __tablename__ = "security_feed"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    event_type: str = Field(max_length=50, index=True)
    severity: str = Field(max_length=20)
    count: int = Field(default=1)
    first_seen: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    last_seen: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    affected_users: List[str] = Field(default=[], sa_column=Column(postgresql.JSONB(astext_type=str)))
    status: str = Field(default="new", max_length=20)  # new, investigating, resolved, ignored
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))


class Task(SQLModel, table=True):
    """A student's short-lived task.

    A task is alive for one day: for the first 24 hours it can be edited and
    marked complete, after that it only shows as expired, and 48 hours after
    creation the row is purged (the list read sweeps it away). The optional
    alarm - remind_at - may only point into the upcoming 24 hours, because a
    tracker this short-lived has no use for a next-week reminder.
    """

    __tablename__ = "task"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="core.user.id", index=True)
    title: str = Field(max_length=200)
    #: The alarm instant, if the student set one. Always inside 24h ahead.
    remind_at: Optional[datetime] = Field(
        default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=True)
    )
    #: Set the moment the student ticks it done; a completed task is final.
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=True)
    )
    #: Creation instant. 24h later the task expires, 48h later it is deleted.
    created_at: datetime = Field(
        default=None,
        sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    #: created_at + 24h, frozen at insert so expiry never drifts.
    expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=True)
    )
