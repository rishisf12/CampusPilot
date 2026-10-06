"""
Team and hackathon routes.

Response shapes follow CampusPilot: a bare object for detail routes,
`{"pagination": {...}, "data": [...]}` for lists.
"""
import datetime
import math
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, func, select

from core.database import get_session
from models import (
    Hackathon,
    JoinRequest,
    Team,
    TeamMember,
    User,
    UserProfile,
    normalize_tags,
)
from core.deps import get_current_user
from features.teams import matching as teams_service
from features.teams import feed
from core.config import get_settings
from fastapi.responses import FileResponse
from pathlib import Path

settings = get_settings()

router = APIRouter()
hackathons_router = APIRouter()


# --------------------------------------------------------------- schemas


class ProfileOut(BaseModel):
    id: int
    full_name: Optional[str] = None
    branch: str
    semester: int
    section: Optional[str] = None
    skills: List[str] = []
    bio: Optional[str] = None


class MemberOut(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str] = None
    username: str
    branch: Optional[str] = None
    skills: List[str] = []
    is_admin: bool
    is_approved: bool

    model_config = {"from_attributes": True}


class HackathonOut(BaseModel):
    id: int
    title: str
    ends_at: Optional[datetime.datetime] = None
    is_active: bool = True
    is_featured: bool = False

    model_config = {"from_attributes": True}


class TeamOut(BaseModel):
    id: int
    name: str
    description: str
    tech_stack: List[str] = []
    wanted: List[str] = []
    max_members: int
    request_to_join: bool
    is_open: bool
    hackathon_id: Optional[int] = None
    hackathon: Optional[HackathonOut] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    owner_branch: Optional[str] = None
    members_count: int = 0
    spots_left: int = 0
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class TeamDetailOut(TeamOut):
    members: List[MemberOut] = []


class MatchOut(BaseModel):
    score: float
    fill_pct: float
    overlap_pct: float
    coverage_pct: float
    branch_bonus: float
    team_gap: List[str] = []
    matching_skills: List[str] = []
    missing_skills: List[str] = []
    fills_gaps: List[str] = []
    same_branch: bool
    reason: str
    members_count: int
    spots_left: int
    team: TeamOut


class MyTeamOut(BaseModel):
    team: TeamOut
    members_count: int
    is_owner: bool
    role: str


class RequestOut(BaseModel):
    id: int
    status: str
    message: Optional[str] = None
    created_at: datetime.datetime
    team_name: str
    user_name: Optional[str] = None
    user_branch: Optional[str] = None

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=1000)
    tech_stack: List[str] = Field(default_factory=list)
    wanted: List[str] = Field(default_factory=list)
    max_members: int = Field(default=4, ge=2, le=20)
    request_to_join: bool = False
    hackathon_id: Optional[int] = None

    @field_validator("tech_stack", "wanted")
    @classmethod
    def _clean_tags(cls, value: List[str]) -> List[str]:
        return normalize_tags(value)


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=80)
    description: Optional[str] = Field(default=None, max_length=1000)
    tech_stack: Optional[List[str]] = None
    wanted: Optional[List[str]] = None
    max_members: Optional[int] = Field(default=None, ge=2, le=20)
    request_to_join: Optional[bool] = None
    is_open: Optional[bool] = None

    @field_validator("tech_stack", "wanted")
    @classmethod
    def _clean_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return normalize_tags(value) if value is not None else None


class HackathonCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=2000)
    link: Optional[str] = None
    tech_stack: List[str] = Field(default_factory=list)
    starts_at: Optional[datetime.datetime] = None
    ends_at: Optional[datetime.datetime] = None
    is_featured: bool = False

    @field_validator("tech_stack")
    @classmethod
    def _clean_stack(cls, value: List[str]) -> List[str]:
        return normalize_tags(value)


class DecisionBody(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid(cls, value: str) -> str:
        if value not in {"accepted", "rejected"}:
            raise ValueError("status must be 'accepted' or 'rejected'")
        return value


# ---------------------------------------------------------------- helpers


def _members_count_map(session: Session, team_ids: List[int]) -> dict:
    if not team_ids:
        return {}
    rows = session.exec(select(TeamMember.team_id).where(TeamMember.team_id.in_(team_ids))).all()
    counts: dict = {}
    for row in rows:
        counts[row] = counts.get(row, 0) + 1
    return counts


def _owner_branches(session: Session, owner_ids: List[int]) -> dict:
    if not owner_ids:
        return {}
    profiles = session.exec(
        select(UserProfile).where(UserProfile.user_id.in_(owner_ids))
    ).all()
    return {p.user_id: p.branch for p in profiles if p.user_id is not None}


def _owner_names(session: Session, owner_ids: List[int]) -> dict:
    if not owner_ids:
        return {}
    users = session.exec(select(User).where(User.id.in_(owner_ids))).all()
    return {u.id: (u.full_name or u.username) for u in users}


def _decorate(session: Session, team: Team, hackathons: Optional[dict] = None) -> TeamOut:
    """Wrap a Team row with counts, owner display fields and its hackathon."""
    counts = _members_count_map(session, [team.id])
    branches = _owner_branches(session, [team.owner_id] if team.owner_id else [])
    names = _owner_names(session, [team.owner_id] if team.owner_id else [])
    out = TeamOut.model_validate(team)
    members_count = counts.get(team.id, 0)
    out.members_count = members_count
    out.spots_left = max(0, (team.max_members or 0) - members_count)
    out.owner_branch = branches.get(team.owner_id) if team.owner_id else None
    out.owner_name = names.get(team.owner_id) if team.owner_id else None
    if team.hackathon_id:
        lookup = hackathons if hackathons is not None else _hackathon_map(session, [team.hackathon_id])
        found = lookup.get(team.hackathon_id)
        if found is not None:
            out.hackathon = HackathonOut.model_validate(found)
    return out


def _hackathon_map(session: Session, ids: List[Optional[int]]) -> dict:
    clean = [i for i in ids if i is not None]
    if not clean:
        return {}
    rows = session.exec(select(Hackathon).where(Hackathon.id.in_(clean))).all()
    return {row.id: row for row in rows if row.id is not None}


def _decorate_many(session: Session, teams: List[Team]) -> List[TeamOut]:
    """Batch wrapper so a grid of teams does not fan out into N+1 queries."""
    if not teams:
        return []
    hackathons = _hackathon_map(session, [t.hackathon_id for t in teams])
    return [_decorate(session, t, hackathons) for t in teams]


def _paginate(page: int, size: int, total: int) -> dict:
    pages = (total + size - 1) // size if size else 1
    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
        "has_next": page < pages,
        "has_previous": page > 1,
    }


def _is_member(session: Session, team_id: int, user_id: int) -> bool:
    return (
        session.exec(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.user_id == user_id
            )
        ).first()
        is not None
    )


def _get_team_or_404(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


# ------------------------------------------------------------------ teams


@router.get("")
def list_teams(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    branch: Optional[str] = None,
    is_open: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    query = select(Team)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            func.lower(Team.name).like(pattern) | func.lower(Team.description).like(pattern)
        )
    if is_open is not None:
        query = query.where(Team.is_open == is_open)

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(
        query.order_by(Team.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()

    # Branch filter applies to the team owner's branch, resolved in one query.
    if branch:
        profiles = session.exec(select(UserProfile)).all()
        by_user = {p.user_id: p.branch for p in profiles if p.user_id is not None}
        rows = [t for t in rows if by_user.get(t.owner_id) == branch]

    return {
        "pagination": _paginate(page, size, total),
        "data": [t.model_dump() for t in _decorate_many(session, rows)],
    }


@router.get("/match")
def match_teams(
    hackathon_id: Optional[int] = Query(None),
    recruiting_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    """
    Ranked teams for the current user, best match first.

    `hackathon_id` narrows to one event; `recruiting_only` hides full teams.
    """
    ranked = teams_service.score_teams_for_user(
        session, current_user, hackathon_id=hackathon_id, recruiting_only=recruiting_only
    )
    decorated = _decorate_many(session, [item["team"] for item in ranked])
    return {
        "matches": [
            {
                **team_out.model_dump(),
                "score": item["score"],
                "fill_pct": item["fill_pct"],
                "overlap_pct": item["overlap_pct"],
                "coverage_pct": item["coverage_pct"],
                "branch_bonus": item["branch_bonus"],
                "team_gap": item["team_gap"],
                "matching_skills": item["matching_skills"],
                "missing_skills": item["missing_skills"],
                "fills_gaps": item["fills_gaps"],
                "same_branch": item["same_branch"],
                "reason": item["reason"],
            }
            for item, team_out in zip(ranked, decorated)
        ]
    }


@router.get("/mine")
def my_teams(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    rows = teams_service.my_teams(session, current_user)
    decorated = _decorate_many(session, [item["team"] for item in rows])
    return {
        "teams": [
            {
                **team_out.model_dump(),
                "members_count": item["members_count"],
                "is_owner": item["is_owner"],
                "role": item["role"],
            }
            for item, team_out in zip(rows, decorated)
        ]
    }


@router.get("/requests")
def list_my_incoming_requests(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    """Join requests waiting on teams the current user owns."""
    rows = teams_service.pending_requests_for_owner(session, current_user)
    return {
        "requests": [
            {
                "id": item["request"].id,
                "status": item["request"].status,
                "message": item["request"].message,
                "created_at": item["request"].created_at,
                "team_name": item["team"].name,
                "user_name": (item["user"].full_name or item["user"].username)
                if item["user"]
                else None,
                "user_branch": (
                    session.exec(
                        select(UserProfile).where(UserProfile.user_id == item["request"].user_id)
                    ).first().branch
                    if item["request"].user_id
                    else None
                ),
            }
            for item in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    if session.exec(select(Team).where(func.lower(Team.name) == payload.name.lower())).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team name already taken")

    if payload.hackathon_id and session.get(Hackathon, payload.hackathon_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown hackathon")

    team = Team(
        name=payload.name,
        description=payload.description,
        tech_stack=payload.tech_stack,
        wanted=payload.wanted,
        max_members=payload.max_members,
        request_to_join=payload.request_to_join,
        is_open=True,
        hackathon_id=payload.hackathon_id,
        owner_id=current_user.id,
    )
    session.add(team)
    session.commit()
    session.refresh(team)

    session.add(TeamMember(team_id=team.id, user_id=current_user.id, is_admin=True))
    session.commit()

    return _decorate(session, team).model_dump()


@router.get("/{team_id}")
def get_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    team = _get_team_or_404(session, team_id)

    members = session.exec(
        select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.joined_at)
    ).all()
    user_ids = [m.user_id for m in members if m.user_id is not None]
    users = session.exec(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    profiles = (
        session.exec(select(UserProfile).where(UserProfile.user_id.in_(user_ids))).all()
        if user_ids
        else []
    )
    users_by_id = {u.id: u for u in users}
    profiles_by_id = {p.user_id: p for p in profiles}

    detail = TeamDetailOut.model_validate(_decorate(session, team).model_dump())
    detail.members = [
        MemberOut(
            id=m.id,
            user_id=m.user_id or 0,
            username=users_by_id[m.user_id].username if m.user_id in users_by_id else "unknown",
            full_name=(
                users_by_id[m.user_id].full_name if m.user_id in users_by_id else None
            ),
            branch=(
                profiles_by_id[m.user_id].branch if m.user_id in profiles_by_id else None
            ),
            skills=(
                normalize_tags(profiles_by_id[m.user_id].skills)
                if m.user_id in profiles_by_id
                else []
            ),
            is_admin=m.is_admin,
            is_approved=m.is_approved,
        )
        for m in members
    ]
    return detail.model_dump()


@router.put("/{team_id}")
def update_team(
    team_id: int,
    payload: TeamUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    team = _get_team_or_404(session, team_id)
    if team.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can edit this team")

    changes = payload.model_dump(exclude_none=True)
    name = changes.pop("name", None)
    if name and name.lower() != (team.name or "").lower():
        clash = session.exec(select(Team).where(func.lower(Team.name) == name.lower())).first()
        if clash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team name already taken")

    for field, value in changes.items():
        setattr(team, field, value)
    if name:
        team.name = name

    session.add(team)
    session.commit()
    session.refresh(team)
    return _decorate(session, team).model_dump()


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    team = _get_team_or_404(session, team_id)
    if team.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete this team")

    for model in (TeamMember, JoinRequest):
        for row in session.exec(select(model).where(model.team_id == team_id)).all():
            session.delete(row)
    session.delete(team)
    session.commit()
    return {"message": "Team deleted"}


@router.get("/{team_id}/members")
def list_team_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    return {"members": get_team(team_id, current_user, session)["members"]}


@router.post("/{team_id}/join")
def join_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    team = _get_team_or_404(session, team_id)

    if team.owner_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already own this team")
    if not team.is_open:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This team is closed")
    if _is_member(session, team_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already in this team")

    members_count = _members_count_map(session, [team_id]).get(team_id, 0)
    if members_count >= team.max_members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This team is full")

    existing = session.exec(
        select(JoinRequest).where(
            JoinRequest.team_id == team_id,
            JoinRequest.user_id == current_user.id,
            JoinRequest.status == "pending",
        )
    ).first()
    if existing:
        return {"status": "pending", "detail": "Request already sent"}

    if team.request_to_join:
        session.add(JoinRequest(team_id=team_id, user_id=current_user.id, status="pending"))
        session.commit()
        return {"status": "pending", "detail": "Join request sent"}

    session.add(TeamMember(team_id=team_id, user_id=current_user.id))
    session.commit()
    return {"status": "joined", "detail": "You joined the team"}


@router.post("/{team_id}/leave")
def leave_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    team = _get_team_or_404(session, team_id)
    if team.owner_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The owner cannot leave. Delete the team instead.")

    membership = session.exec(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == current_user.id)
    ).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not in this team")

    session.delete(membership)
    session.commit()
    return {"message": "Left the team"}


@router.put("/requests/{request_id}")
def decide_request(
    request_id: int,
    payload: DecisionBody,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    request_row = session.get(JoinRequest, request_id)
    if request_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    team = session.get(Team, request_row.team_id)
    if team is None or team.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the team owner can respond")

    if request_row.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already handled")

    if payload.status == "accepted":
        if _is_member(session, team.id, request_row.user_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member")
        members_count = _members_count_map(session, [team.id]).get(team.id, 0)
        if members_count >= team.max_members:
            team.is_open = False
            session.add(team)
            request_row.status = "rejected"
        else:
            session.add(TeamMember(team_id=team.id, user_id=request_row.user_id))
            request_row.status = "accepted"

    request_row.responded_at = datetime.datetime.utcnow()
    session.add(request_row)
    session.commit()
    return {"message": f"Request {request_row.status}", "id": request_row.id, "status": request_row.status}


# ------------------------------------------------------------- hackathons


@hackathons_router.get("")
def list_hackathons(
    is_active: Optional[bool] = None,
    is_featured: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    """
    The hackathon feed, newest first.

    Hard-limited to the retention window. `purge_expired` actually deletes the
    rows; this filter means an entry disappears from the feed the moment it
    ages out even if no sweep has run yet.
    """
    query = select(Hackathon).where(Hackathon.created_at >= feed.cutoff())
    if is_active is not None:
        query = query.where(Hackathon.is_active == is_active)
    if is_featured is not None:
        query = query.where(Hackathon.is_featured == is_featured)
    rows = session.exec(query.order_by(Hackathon.created_at.desc())).all()

    stats = teams_service.hackathon_recruitment(session, [r.id for r in rows])
    now = datetime.datetime.utcnow()
    retention = datetime.timedelta(days=settings.feed_retention_days)

    return {
        "retention_days": settings.feed_retention_days,
        "feed_enabled": settings.feed_enabled,
        "hackathons": [
            {
                "id": r.id,
                # Coerces the JSON columns to lists: an unset one reads back as
                # None on an instance that never went through the field
                # validators, because the server default only applies at
                # INSERT. Without this the response omits `links` entirely and
                # the frontend has to guard every list field.
                **{
                    c: ([] if isinstance(getattr(r, c, None), list) and getattr(r, c) is None else getattr(r, c))
                    for c in Hackathon.model_fields
                    if c != "id"
                },
                "attachments": [
                    {
                        "name": stored,
                        "url": f"/hackathons/media/{stored}",
                        "size": _media_size(stored),
                    }
                    for stored in (r.attachments or [])
                ],
                # Days until this entry is swept, measured per row from its own
                # arrival. The old form (`cutoff() + retention`) is by
                # definition `now`, so every entry reported zero.
                #
                # `created_at` carries a server default of `func.now()`, which
                # SQLite evaluates per statement, so a row committed moments ago
                # is already a few hundredths of a second in the past. Flooring
                # that away would report 29 for a brand-new entry, so the
                # remainder is rounded up and the count only drops once a whole
                # day has genuinely passed.
                "expires_in_days": max(
                    0,
                    math.ceil((r.created_at + retention - now).total_seconds() / 86400),
                ),
                **stats.get(r.id, {"teams": 0, "open_teams": 0, "spots_left": 0}),
            }
            for r in rows
        ],
    }


def _media_size(stored: str) -> int:
    try:
        return (Path(settings.feed_media_dir) / str(stored)).stat().st_size
    except OSError:
        return 0


@hackathons_router.post("/feed/sync")
def sync_feed(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    """
    Pull new mail and sweep anything past the retention window.

    A button rather than a background job: no scheduler dependency is added, and
    the user can see when the last pull happened. Returns the importer's own
    summary so an unconfigured mailbox explains itself instead of failing.
    """
    return feed.ingest_and_purge(session)


@hackathons_router.get("/media/{name}")
def get_feed_media(name: str, current_user: User = Depends(get_current_user)) -> Any:
    """
    Serve one attachment.

    The name is resolved and then checked against the media directory, so a
    crafted `../../` cannot escape it even though stored names are generated.
    """
    base = Path(settings.feed_media_dir).resolve()
    target = (base / str(name)).resolve()
    if target.parent != base or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    stored_name = target.name
    return FileResponse(
        target,
        # Attachments are untrusted uploads, so force a download rather than
        # letting the browser sniff and render them inline.
        headers={"Content-Disposition": f'attachment; filename="{stored_name}"'},
    )


@hackathons_router.post("", status_code=status.HTTP_201_CREATED)
def create_hackathon(
    payload: HackathonCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    hackathon = Hackathon(
        title=payload.title,
        description=payload.description,
        link=payload.link,
        tech_stack=payload.tech_stack,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_featured=payload.is_featured,
        created_by=current_user.id,
    )
    session.add(hackathon)
    session.commit()
    session.refresh(hackathon)
    return {"id": hackathon.id, **{c: getattr(hackathon, c) for c in Hackathon.model_fields if c != "id"}}