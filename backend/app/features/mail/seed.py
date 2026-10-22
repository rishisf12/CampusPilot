"""
Seed data for the mail app.

Idempotent: everything is looked up first, so running this twice never
creates duplicates. Safe to run on a development database at any time.

Seeds:

* the sections each group runs (academics, placement, cultural, technical,
  sports, other) - same ids as the "Important" navigation;
* demo clusters per group, so a fresh dev database shows a mailbox that
  files itself the way the college intends;
* a sample user per role with section access.
"""
import logging
from typing import Dict, List, Optional

from sqlmodel import Session, select

from features.mail.models import MailCluster, MailSection, MailSectionAccess, MailSenderRule
from models import User, UserProfile, UserRole
from features.auth.routes import create_access_token

logger = logging.getLogger(__name__)

#: The sections a group runs, in the order they are taught out. The keys
#: match the "Important" navigation ids.
DEFAULT_SECTIONS = (
    ("academics", "Academics", "Notices from the registrar and the departments"),
    ("placement", "Placement Cell", "Drives, internships and the career cell"),
    ("cultural", "Cultural", "The cultural club and the festival season"),
    ("technical", "Technical", "Technical festivals, hackathons and workshops"),
    ("sports", "Sports", "The sports season and inter-hostel tournaments"),
    ("other", "Other", "Everything the college writes that fits nowhere else"),
)

DEFAULT_GROUPS = ("ug", "pg")

#: Demo clusters: the college's own offices, with the addresses they write
#: from. A fresh development database starts with these; a real college
#: replaces them from the admin console.
DEMO_CLUSTERS = (
    {
        "name": "Registrar",
        "section": "academics",
        "description": "The registrar's office and the examination cell",
        "members": (
            "registrar@iiitdmj.ac.in",
            "examcell@iiitdmj.ac.in",
            "academic@iiitdmj.ac.in",
        ),
    },
    {
        "name": "Training and Placement Cell",
        "section": "placement",
        "description": "Drives, internships and the career office",
        "members": (
            "tnp@iiitdmj.ac.in",
            "placement@iiitdmj.ac.in",
            "internship@iiitdmj.ac.in",
        ),
    },
    {
        "name": "Cultural Club",
        "section": "cultural",
        "description": "The cultural club and the festival coordinators",
        "members": (
            "cultural-club@iiitdmj.ac.in",
            "cultural@iiitdmj.ac.in",
        ),
    },
    {
        "name": "Tech Fest Team",
        "section": "technical",
        "description": "The technical festival and the hackathon cell",
        "members": (
            "tech-fest@iiitdmj.ac.in",
            "technical@iiitdmj.ac.in",
            "hackathon@iiitdmj.ac.in",
        ),
    },
    {
        "name": "Sports Office",
        "section": "sports",
        "description": "The sports season and the inter-hostel tournaments",
        "members": (
            "sports-office@iiitdmj.ac.in",
            "sports@iiitdmj.ac.in",
        ),
    },
)


def seed_sections(session: Session, groups: Optional[List[str]] = None) -> Dict[str, int]:
    """The sections, once per group. Returns {group: count}."""
    wanted = tuple(groups or DEFAULT_GROUPS)
    for group in wanted:
        for order, (key, label, description) in enumerate(DEFAULT_SECTIONS):
            existing = session.exec(
                select(MailSection).where(
                    MailSection.group == group,
                    MailSection.key == key,
                )
            ).first()
            if existing is not None:
                continue
            session.add(
                MailSection(
                    group=group,
                    key=key,
                    label=label,
                    description=description,
                    sort_order=order,
                    is_public=True,
                )
            )
    session.commit()
    return {group: len(DEFAULT_SECTIONS) for group in wanted}


def seed_demo_clusters(session: Session, group: str = "ug") -> int:
    """The demo clusters for one group. Returns how many were created."""
    created = 0
    for demo in DEMO_CLUSTERS:
        cluster = session.exec(
            select(MailCluster).where(
                MailCluster.group == group,
                MailCluster.name == demo["name"],
            )
        ).first()
        if cluster is None:
            cluster = MailCluster(
                group=group,
                name=demo["name"],
                section=demo["section"],
                description=demo["description"],
            )
            session.add(cluster)
            session.commit()
            session.refresh(cluster)
            created += 1
        for member in demo["members"]:
            existing = session.exec(
                select(MailSenderRule).where(
                    MailSenderRule.group == group,
                    MailSenderRule.pattern == member.lower(),
                )
            ).first()
            if existing is not None:
                if existing.cluster_id != cluster.id:
                    existing.cluster_id = cluster.id
                    existing.section = cluster.section
                    session.add(existing)
                continue
            session.add(
                MailSenderRule(
                    group=group,
                    pattern=member.lower(),
                    section=cluster.section,
                    cluster_id=cluster.id,
                    kind="exact",
                )
            )
    session.commit()
    return created


def grant_section_access(
    session: Session,
    user_id: int,
    section_keys: List[str],
    group: str = "ug",
    can_manage: bool = False,
) -> int:
    """Give an account access to some sections. Returns how many were granted."""
    granted = 0
    for key in section_keys:
        section = session.exec(
            select(MailSection).where(
                MailSection.group == group,
                MailSection.key == key,
            )
        ).first()
        if section is None:
            continue
        existing = session.exec(
            select(MailSectionAccess).where(
                MailSectionAccess.user_id == user_id,
                MailSectionAccess.section_id == section.id,
            )
        ).first()
        if existing is not None:
            if can_manage and not existing.can_manage:
                existing.can_manage = True
                session.add(existing)
            continue
        session.add(
            MailSectionAccess(
                user_id=user_id,
                section_id=section.id,
                can_read=True,
                can_manage=can_manage,
            )
        )
        granted += 1
    session.commit()
    return granted


def seed_all(session: Session, groups: Optional[List[str]] = None) -> Dict[str, int]:
    """Everything: sections and demo clusters for each group."""
    wanted = tuple(groups or DEFAULT_GROUPS)
    sections = seed_sections(session, list(wanted))
    clusters = {group: seed_demo_clusters(session, group) for group in wanted}
    return {"sections": sections, "clusters": clusters}
