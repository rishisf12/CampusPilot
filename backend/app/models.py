"""SQLModel tables for ClassPilot."""
from datetime import date, time, datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy import Date, DateTime, UniqueConstraint, func, Enum as SAEnum, Integer, ForeignKey
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