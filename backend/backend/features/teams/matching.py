"""
Skill matching.

The question this module answers is not "who resembles this team" but "who
completes it". A team that is recruiting wants somebody who closes a gap its
current members have not covered, not somebody who duplicates them.

Scoring combines two signals:

    fill     what share of the team's remaining gap this candidate closes. The
             gap is (tech stack | wanted) minus the skills the current members
             already bring, so joining the same team twice stops looking
             attractive as more people join it. This is the deciding term.
    overlap  Jaccard of the candidate's skills against the team's tech stack -
             familiarity, worth a small amount and used mainly as a tie-break.

The branch bonus is the part this app adds over UrTeam. MyTeam is scoped to a
single college, so "same branch" is real signal that a skill-only model has no
way to express: a flat 15 points, clamped so the total never exceeds 100.

Jaccard itself is the core borrowed from UrTeam and is unchanged: normalize
both sides, then |A n B| / |A u B|, returning 0.0 on an empty union so a user
with no skills never divides by zero.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from core.config import get_settings
from models import Hackathon, JoinRequest, Team, TeamMember, User, UserProfile, normalize_tags

logger = logging.getLogger(__name__)
settings = get_settings()


def jaccard(a: Optional[List[str]], b: Optional[List[str]]) -> float:
    """Jaccard similarity as a 0..1 fraction. Empty union -> 0.0."""
    set_a = set(normalize_tags(a))
    set_b = set(normalize_tags(b))
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def score_team(
    user_skills: Optional[List[str]],
    tech_stack: Optional[List[str]],
    wanted: Optional[List[str]] = None,
    member_skills: Optional[List[str]] = None,
    same_branch: bool = False,
) -> Dict[str, Any]:
    """
    Score one team for one user.

    The question is not "who resembles this team" - it is "who completes it".

    gap        what the team still lacks: its tech stack plus its wish list,
               minus the skills its current members already bring.
    fills      the part of that gap this candidate closes.
    overlap    Jaccard against the tech stack - familiarity, a secondary signal.

    Gap-filling is weighted 0.85 against 0.15 for familiarity. A plain weighted
    sum cannot make one signal dominate when the two are mutually exclusive:
    when a candidate who duplicates the stack is set against one who owns the
    missing skill, any weighting that lets 100% overlap win is not measuring
    what a team needs when it recruits another member.

    `member_skills` is what makes this a team-finder rather than a similarity
    search: it is the union of the current members' skills, so joining the same
    team twice stops looking attractive as that team grows.
    """
    skills = set(normalize_tags(user_skills))
    stack = set(normalize_tags(tech_stack))
    wanted_set = set(normalize_tags(wanted))
    covered = set(normalize_tags(member_skills))

    need = stack | wanted_set
    gap = need - covered
    fills = sorted(skills & gap)
    matching = sorted(skills & stack)
    missing = sorted(stack - skills)

    overlap_pct = jaccard(user_skills, tech_stack) * 100.0

    # An empty gap means two very different things, and conflating them is a
    # real bug rather than a cosmetic one:
    #
    #   the team declared nothing at all  -> no information, so fall back to
    #                                        familiarity and let the score come
    #                                        from what is known
    #   the team is fully covered in skills -> there is genuinely nothing left
    #                                        to contribute, so fill is 0
    #
    # Returning 100 for both makes a fully-staffed team a top match for every
    # stranger who ever looks at it, which is the similarity-search failure this
    # scorer exists to avoid, just pointing the other way.
    if not need:
        fill_pct = overlap_pct
    elif gap:
        fill_pct = len(fills) / len(gap) * 100.0
    else:
        fill_pct = 0.0

    # Reported for the UI, but deliberately not a third scoring term: the wish
    # list is already inside `gap`, so scoring it again double-counts the same
    # evidence and punishes teams that never published one.
    coverage_pct = (
        (len(skills & wanted_set) / len(wanted_set) * 100.0) if wanted_set else 0.0
    )

    bonus = settings.branch_match_bonus if same_branch else 0.0
    # Gap-filling is weighted 0.85 against 0.15 for familiarity, and the
    # imbalance is the point. Overlap with the existing stack is worth little
    # once members already cover it: at any higher weight a candidate who
    # duplicates the stack outranks one who owns the missing skill, which is
    # precisely backwards for a team recruiting another member. Overlap earns
    # its place only as a tie-break between equally useful candidates.
    blended = 0.85 * fill_pct + 0.15 * overlap_pct
    score = min(100.0, round(blended + bonus, 1))

    return {
        "score": score,
        "fill_pct": round(fill_pct, 1),
        "overlap_pct": round(overlap_pct, 1),
        "coverage_pct": round(coverage_pct, 1),
        "branch_bonus": round(bonus, 1),
        "team_gap": sorted(gap),
        "matching_skills": matching,
        "missing_skills": missing,
        "fills_gaps": fills,
        "same_branch": same_branch,
        "reason": _explain(fills, gap, matching),
    }


def _explain(fills: List[str], gap: set, matching: List[str]) -> str:
    """One line saying what this candidate would actually add."""
    if fills:
        base = f"You bring {', '.join(fills)} - the team is short on it"
        remaining = sorted(gap - set(fills))
        if remaining:
            return f"{base} (still missing {', '.join(remaining)})"
        return f"{base}. That completes their stack"
    if not gap:
        return "Their stack is already covered"
    if matching:
        return f"You know {', '.join(matching[:3])}, but so does everyone already there"
    return "Nothing in their gap yet"


def _profile_for(session: Session, user_id: Optional[int]) -> Optional[UserProfile]:
    if user_id is None:
        return None
    return session.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()


def hackathon_recruitment(session: Session, hackathon_ids: List[Optional[int]]) -> Dict[int, Dict[str, int]]:
    """
    Per-hackathon team and vacancy counts.

    An event page that cannot say how many teams are still recruiting is just a
    poster. One grouped pass over teams plus one over members, so a grid of
    events does not fan out into N+1 queries.
    """
    clean = [i for i in hackathon_ids if i is not None]
    if not clean:
        return {}

    teams = session.exec(select(Team).where(Team.hackathon_id.in_(clean))).all()
    stats: Dict[int, Dict[str, int]] = {
        hid: {"teams": 0, "open_teams": 0, "spots_left": 0} for hid in clean
    }

    for team in teams:
        if team.hackathon_id is None:
            continue
        bucket = stats[team.hackathon_id]
        bucket["teams"] += 1
        if team.is_open:
            bucket["open_teams"] += 1

    if not teams:
        return stats

    counts = _member_counts(session, [t.id for t in teams if t.id is not None])
    for team in teams:
        if team.hackathon_id is None or team.id is None:
            continue
        if not team.is_open:
            continue
        vacancies = max(0, (team.max_members or 0) - counts.get(team.id, 0))
        stats[team.hackathon_id]["spots_left"] += vacancies

    return stats


def _member_counts(session: Session, team_ids: List[int]) -> Dict[int, int]:
    """One grouped query instead of a count per team."""
    if not team_ids:
        return {}
    rows = session.exec(
        select(TeamMember.team_id).where(TeamMember.team_id.in_(team_ids))
    ).all()
    counts: Dict[int, int] = {}
    for row in rows:
        counts[row] = counts.get(row, 0) + 1
    return counts


def _team_member_skills(session: Session, team_ids: List[int]) -> Dict[int, List[str]]:
    """
    Union of the skills each team's current members bring.

    This is what turns a similarity search into a team-finder: the gap a team
    still has is measured against what its members already cover, not against a
    static wish list.
    """
    if not team_ids:
        return {}
    members = session.exec(
        select(TeamMember).where(
            TeamMember.team_id.in_(team_ids), TeamMember.is_approved == True  # noqa: E712
        )
    ).all()
    user_ids = [m.user_id for m in members if m.user_id is not None]
    if not user_ids:
        return {}

    profiles = session.exec(
        select(UserProfile).where(UserProfile.user_id.in_(user_ids))
    ).all()
    skills_by_user: Dict[int, List[str]] = {
        p.user_id: normalize_tags(p.skills) for p in profiles if p.user_id is not None
    }

    by_team: Dict[int, List[str]] = {}
    for member in members:
        if member.team_id is None:
            continue
        bucket = by_team.setdefault(member.team_id, [])
        for skill in skills_by_user.get(member.user_id, []):
            if skill not in bucket:
                bucket.append(skill)
    return by_team


def score_teams_for_user(
    session: Session,
    user: User,
    hackathon_id: Optional[int] = None,
    recruiting_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Rank every joinable team for `user`, best first.

    Own teams are excluded - you cannot "match" with yourself.

    `hackathon_id` narrows the ranking to one event, which is the question a
    student actually asks before a deadline: "who is still recruiting for the
    hackathon I am entering?"
    """
    viewer_profile = _profile_for(session, user.id)
    viewer_skills = normalize_tags(viewer_profile.skills if viewer_profile else [])
    viewer_branch = viewer_profile.branch if viewer_profile else None

    query = select(Team)
    if hackathon_id is not None:
        query = query.where(Team.hackathon_id == hackathon_id)
    if recruiting_only:
        query = query.where(Team.is_open == True)  # noqa: E712

    teams = session.exec(query.order_by(Team.created_at.desc())).all()
    if not teams:
        return []

    # One pass over owners to resolve branches without an N+1 query.
    owner_ids = {t.owner_id for t in teams if t.owner_id is not None}
    owner_branch: Dict[int, str] = {}
    if owner_ids:
        profiles = session.exec(
            select(UserProfile).where(UserProfile.user_id.in_(list(owner_ids)))
        ).all()
        owner_branch = {p.user_id: p.branch for p in profiles if p.user_id is not None}

    counts = _member_counts(session, [t.id for t in teams if t.id is not None])
    member_skills = _team_member_skills(session, [t.id for t in teams if t.id is not None])

    hackathons = _hackathons_by_id(session, [t.hackathon_id for t in teams if t.hackathon_id])

    results: List[Dict[str, Any]] = []
    for team in teams:
        if team.owner_id == user.id:
            continue

        same_branch = bool(viewer_branch) and viewer_branch == owner_branch.get(team.owner_id)
        scored = score_team(
            viewer_skills,
            team.tech_stack,
            team.wanted,
            member_skills.get(team.id, []),
            same_branch,
        )
        scored["team"] = team
        scored["members_count"] = counts.get(team.id, 0)
        scored["spots_left"] = max(0, (team.max_members or 0) - counts.get(team.id, 0))
        scored["hackathon"] = hackathons.get(team.hackathon_id)
        results.append(scored)

    results.sort(key=lambda item: (-item["score"], item["team"].name or ""))
    return results


def _hackathons_by_id(session: Session, ids: List[Optional[int]]) -> Dict[int, Hackathon]:
    clean = [i for i in ids if i is not None]
    if not clean:
        return {}
    rows = session.exec(select(Hackathon).where(Hackathon.id.in_(clean))).all()
    return {row.id: row for row in rows if row.id is not None}


def my_teams(session: Session, user: User) -> List[Dict[str, Any]]:
    """Teams the user owns or belongs to, with their member counts."""
    memberships = session.exec(
        select(TeamMember).where(TeamMember.user_id == user.id)
    ).all()

    team_ids = [m.team_id for m in memberships if m.team_id is not None]
    if not team_ids:
        return []

    owned = session.exec(select(Team).where(Team.owner_id == user.id)).all()
    by_id: Dict[int, Team] = {t.id: t for t in owned if t.id is not None}
    teams = session.exec(select(Team).where(Team.id.in_(team_ids))).all()
    for team in teams:
        if team.id is not None:
            by_id[team.id] = team

    counts = _member_counts(session, list(by_id.keys()))
    admin_team_ids = {m.team_id for m in memberships if m.is_admin}

    out: List[Dict[str, Any]] = []
    for team in sorted(by_id.values(), key=lambda t: t.created_at or 0, reverse=True):
        out.append(
            {
                "team": team,
                "members_count": counts.get(team.id, 0),
                "is_owner": team.owner_id == user.id,
                "role": "owner" if team.owner_id == user.id else ("admin" if team.id in admin_team_ids else "member"),
            }
        )
    return out


def pending_requests_for_owner(session: Session, user: User) -> List[Dict[str, Any]]:
    """Join requests addressed to teams the user owns."""
    owned = session.exec(select(Team).where(Team.owner_id == user.id)).all()
    owned_ids = [t.id for t in owned if t.id is not None]
    if not owned_ids:
        return []

    requests = session.exec(
        select(JoinRequest)
        .where(JoinRequest.team_id.in_(owned_ids), JoinRequest.status == "pending")
        .order_by(JoinRequest.created_at.desc())
    ).all()

    teams_by_id = {t.id: t for t in owned}
    users = session.exec(
        select(User).where(User.id.in_([r.user_id for r in requests if r.user_id is not None]))
    ).all()
    users_by_id = {u.id: u for u in users}

    out: List[Dict[str, Any]] = []
    for request in requests:
        team = teams_by_id.get(request.team_id)
        if team is None:
            continue
        member = users_by_id.get(request.user_id)
        out.append({"request": request, "team": team, "user": member})
    return out