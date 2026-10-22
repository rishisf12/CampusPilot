"""
The mail service: filing, listing, starring, composing.

Everything a section's inbox does, in one place, so the routes stay thin.

Every read is scoped to a **group** - the undergraduate mailbox and the
postgraduate mailbox are different mail, and a group never sees the
other's.

The filing order is the whole point of the app and it is short:

  1. the sender's exact email id is in a cluster   -> that cluster's section
  2. the sender's domain is in a cluster            -> that cluster's section
  3. nothing                                       -> the unassigned state

The receiving address is never part of it. It says which door the mail
came through, not where it belongs.
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlmodel import Session, or_, select

from features.mail.models import (
    MailCluster,
    MailDirection,
    MailFile,
    MailMessage,
    MailSenderRule,
)
from features.mail.sections import (
    GROUP_IDS,
    UNASSIGNED_LABEL,
    UNASSIGNED_SECTION,
    classify,
    group_for_programme,
    is_group,
    is_section,
    is_storable_section,
)
from features.mail.settings import get_mail_settings

logger = logging.getLogger(__name__)

#: How long a snippet is.
SNIPPET_LENGTH = 220


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snippet(body: Optional[str]) -> str:
    """The first lines of a body, on one line."""
    if not body:
        return ""
    text = re.sub(r"\s+", " ", body).strip()
    return text[:SNIPPET_LENGTH]


def message_id_for(
    group: str, from_email: str, subject: str, received_at: Optional[datetime]
) -> str:
    """
    A stable identifier for a message.

    The mail protocol's own Message-ID is best, but a mailbox does not
    always carry one, so a hash of the group, the sender, the subject and
    the arrival time stands in. The group is in the hash because the two
    mailboxes are different mail: the same notice sent to both is two
    messages, and each group files its own copy.
    """
    stamp = received_at.isoformat() if received_at else ""
    digest = hashlib.sha256(
        f"{group}|{from_email.lower()}|{(subject or '').strip().lower()}|{stamp}".encode(
            "utf-8"
        )
    )
    return digest.hexdigest()[:40]


def thread_key(subject: Optional[str]) -> str:
    """
    The conversation a message belongs to.

    A mail app keeps a thread together by what it is about, not by who
    wrote it: the notice and the answer to it share a subject, and the
    prefixes that answer adds ("Re:", "Fwd:") do not change what it is
    about.
    """
    text = (subject or "").strip()
    text = re.sub(r"^(re|fwd|fw)\s*:\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).lower()[:200]


# --------------------------------------------------------------------------
# Filing: where a message lands.
#


@dataclass
class Filing:
    """Where a message lands, and what put it there."""

    section: str
    cluster_id: Optional[int] = None
    pattern: Optional[str] = None
    kind: Optional[str] = None
    rule_id: Optional[int] = None

    @property
    def filed(self) -> bool:
        """True when a cluster decided, false when the sender is unknown."""
        return self.cluster_id is not None or self.rule_id is not None


def _normalise_pattern(pattern: str) -> Tuple[str, str]:
    """
    A sender pattern, normalised, with what it names.

    ``tnp@college.ac.in`` names one sender. ``@college.ac.in`` (or
    ``college.ac.in``) names every sender on that domain.
    """
    normalised = _rule_pattern(pattern)
    if not normalised or " " in normalised or "/" in normalised:
        raise ValueError(f"'{pattern}' is not a sender email id or domain rule.")
    if normalised.startswith("@"):
        if len(normalised) < 2:
            raise ValueError(f"'{pattern}' is not a domain rule.")
        return normalised, "domain"
    if "@" in normalised:
        local, _, domain = normalised.partition("@")
        if not local or not domain:
            raise ValueError(
                f"'{pattern}' is not a sender email id or domain rule."
            )
        return normalised, "exact"
    if "." not in normalised:
        # Neither an address nor a domain: no mail is sent "from" this.
        raise ValueError(f"'{pattern}' is not a sender email id or domain rule.")
    return f"@{normalised}", "domain"


def _rule_pattern(pattern: str) -> str:
    """A sender pattern, normalised to the form the rules are kept in."""
    return (pattern or "").strip().lower().rstrip(".,;")


def _extract_email(from_field: Optional[str]) -> Optional[str]:
    """
    Extract the bare email address from a From field.

    Handles Name <addr@host>, addr@host, and Name <addr@host> (comment).
    Returns None when there is no address to extract.
    """
    if not from_field:
        return None
    text = from_field.strip()
    text = re.sub(r"\s*\([^)]*\)", "", text).strip()
    match = re.search(r"<([^>]+)>", text)
    if match:
        return match.group(1).strip().lower()
    candidate = text.split()[-1] if text.split() else ""
    if "@" in candidate:
        return candidate.lower()
    return None


def _strip_plus_tag(address: str) -> str:
    """Strip a +tag from the local part of an address."""
    if "@" not in address:
        return address
    local, _, domain = address.partition("@")
    if "+" in local:
        local = local[: local.index("+")]
    return f"{local}@{domain}"


# --------------------------------------------------------------------------
# Clusters.
#


def list_clusters(
    session: Session, group: Optional[str] = None
) -> List[MailCluster]:
    """The registered clusters, section by section."""
    stmt = select(MailCluster).order_by(
        MailCluster.group, MailCluster.section, MailCluster.name
    )
    if is_group(group):
        stmt = stmt.where(MailCluster.group == group)
    return list(session.exec(stmt).all())


def get_cluster(session: Session, cluster_id: int) -> Optional[MailCluster]:
    """One cluster by its id."""
    return session.get(MailCluster, cluster_id)


def create_cluster(
    session: Session,
    *,
    group: str,
    name: str,
    section: str,
    description: Optional[str] = None,
    members: Optional[List[str]] = None,
    created_by: Optional[int] = None,
) -> MailCluster:
    """
    Register a cluster: a name, the section it files into, and its senders.

    The members may be given here or added later; either way a sender that
    is already registered is not registered twice.
    """
    if not is_group(group):
        raise ValueError(f"Unknown mail group '{group}'.")
    label = (name or "").strip()
    if not label:
        raise ValueError("A cluster needs a name.")
    if not is_section(section):
        raise ValueError(f"Unknown mail section '{section}'.")
    existing = session.exec(
        select(MailCluster).where(
            MailCluster.group == group,
            func.lower(MailCluster.name) == label.lower(),
        )
    ).first()
    if existing is not None:
        raise ValueError(f"A cluster named '{label}' is already registered.")
    cluster = MailCluster(
        group=group,
        name=label,
        section=section,
        description=(description or "").strip() or None,
        created_by=created_by,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    if members:
        add_cluster_members(session, cluster.id or 0, members, created_by=created_by)
    return cluster


def update_cluster(
    session: Session,
    cluster_id: int,
    *,
    name: Optional[str] = None,
    section: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[MailCluster]:
    """
    Rename a cluster, or move it to another section.

    Moving a cluster moves the mail it filed: the messages keep their place
    in the student's inbox, under the section the cluster now names.
    """
    cluster = get_cluster(session, cluster_id)
    if cluster is None:
        return None
    if name is not None:
        label = name.strip()
        if not label:
            raise ValueError("A cluster needs a name.")
        clash = session.exec(
            select(MailCluster).where(
                MailCluster.group == cluster.group,
                func.lower(MailCluster.name) == label.lower(),
                MailCluster.id != cluster.id,
            )
        ).first()
        if clash is not None:
            raise ValueError(f"A cluster named '{label}' is already registered.")
        cluster.name = label
    if section is not None:
        if not is_section(section):
            raise ValueError(f"Unknown mail section '{section}'.")
        cluster.section = section
    if description is not None:
        cluster.description = description.strip() or None
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    # The members follow the cluster's section, and so does the mail it filed.
    for rule in cluster_members(session, cluster.id or 0):
        rule.section = cluster.section
        session.add(rule)
    session.commit()
    for message in _messages(session, cluster.group):
        if message.cluster_id == cluster.id:
            message.section = cluster.section
            session.add(message)
    session.commit()
    return cluster


def delete_cluster(session: Session, cluster_id: int) -> bool:
    """
    A cluster, unregistered.

    Its senders go with it, and the mail it filed goes back to the
    unassigned state - where it waits for a sender to be registered again.
    """
    cluster = get_cluster(session, cluster_id)
    if cluster is None:
        return False
    for rule in cluster_members(session, cluster.id or 0):
        session.delete(rule)
    for message in _messages(session, cluster.group):
        if message.cluster_id == cluster.id:
            message.cluster_id = None
            message.section = UNASSIGNED_SECTION
            session.add(message)
    session.delete(cluster)
    session.commit()
    return True


def cluster_members(session: Session, cluster_id: int) -> List[MailSenderRule]:
    """The senders registered in one cluster."""
    stmt = (
        select(MailSenderRule)
        .where(MailSenderRule.cluster_id == cluster_id)
        .order_by(MailSenderRule.pattern)
    )
    return list(session.exec(stmt).all())


def add_cluster_members(
    session: Session,
    cluster_id: int,
    patterns: List[str],
    created_by: Optional[int] = None,
) -> List[MailSenderRule]:
    """
    Add senders to a cluster.

    A list pasted in one go is the normal way a cluster is built, so a
    whole list may be given at once. A sender already registered elsewhere
    moves to this cluster rather than being registered twice.
    """
    cluster = get_cluster(session, cluster_id)
    if cluster is None:
        raise ValueError("No such cluster.")
    added: List[MailSenderRule] = []
    for raw in patterns or []:
        normalised, kind = _normalise_pattern(raw)
        existing = session.exec(
            select(MailSenderRule).where(
                MailSenderRule.group == cluster.group,
                MailSenderRule.pattern == normalised,
            )
        ).first()
        if existing is not None:
            existing.cluster_id = cluster.id
            existing.section = cluster.section
            existing.kind = kind
            session.add(existing)
            added.append(existing)
            continue
        rule = MailSenderRule(
            group=cluster.group,
            pattern=normalised,
            section=cluster.section,
            cluster_id=cluster.id,
            kind=kind,
            created_by=created_by,
        )
        session.add(rule)
        added.append(rule)
    session.commit()
    for rule in added:
        session.refresh(rule)
    return added


def remove_cluster_member(session: Session, member_id: int) -> bool:
    """
    One sender out of its cluster.

    The mail it filed goes back to the unassigned state, so nothing is
    filed by a sender nobody registered any more.
    """
    rule = session.get(MailSenderRule, member_id)
    if rule is None:
        return False
    group = rule.group
    pattern = rule.pattern
    session.delete(rule)
    session.commit()
    refile_sender(session, group, pattern)
    return True


# --------------------------------------------------------------------------
# Sender rules (loose registrations).
#


def list_sender_rules(
    session: Session, group: Optional[str] = None
) -> List[MailSenderRule]:
    """The registered sender rules, section by section."""
    stmt = select(MailSenderRule).order_by(
        MailSenderRule.group, MailSenderRule.section
    )
    if is_group(group):
        stmt = stmt.where(MailSenderRule.group == group)
    return list(session.exec(stmt).all())


def create_sender_rule(
    session: Session,
    *,
    group: str,
    pattern: str,
    section: str,
    cluster_id: Optional[int] = None,
    priority: int = 0,
    is_active: bool = True,
    notes: Optional[str] = None,
    created_by: Optional[int] = None,
) -> MailSenderRule:
    """
    Register one sender email id under a section.

    Registering an id that is already registered returns the rule on
    record - the cluster is a set, not a list. A rule may name a single
    sender (``tnp@iiitdmj.ac.in``) or every sender on a domain: with the
    ``@`` (``@iiitdmj.ac.in``) or without it (``iiitdmj.ac.in``).
    """
    if not is_group(group):
        raise ValueError(f"Unknown mail group '{group}'.")
    normalised, kind = _normalise_pattern(pattern)
    if not is_section(section):
        raise ValueError(f"Unknown mail section '{section}'.")
    existing = session.exec(
        select(MailSenderRule).where(
            MailSenderRule.group == group,
            MailSenderRule.pattern == normalised,
        )
    ).first()
    if existing is not None:
        existing.section = section
        existing.cluster_id = cluster_id
        if priority != existing.priority:
            existing.priority = priority
        existing.is_active = is_active
        if notes is not None:
            existing.notes = notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    rule = MailSenderRule(
        group=group,
        pattern=normalised,
        section=section,
        cluster_id=cluster_id,
        kind=kind,
        priority=priority,
        is_active=is_active,
        notes=notes,
        created_by=created_by,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_sender_rule(session: Session, rule_id: int) -> bool:
    """
    One rule, unregistered.

    The mail it filed goes back to the unassigned state, so no message is
    ever filed by a sender nobody registered.
    """
    rule = session.get(MailSenderRule, rule_id)
    if rule is None:
        return False
    group = rule.group
    pattern = rule.pattern
    session.delete(rule)
    session.commit()
    refile_sender(session, group, pattern)
    return True


def match_sender_rule(
    session: Session, group: str, from_email: Optional[str]
) -> Optional[MailSenderRule]:
    """
    The rule that files a sender's mail, if the college registered one.

    A rule for the whole address wins over a rule for its domain, because
    the address is the more specific statement. When a domain would file
    two ways, the first cluster registered for it wins.
    """
    settings = get_mail_settings()
    address = _extract_email(from_email)
    if not address or "@" not in address:
        return None
    if settings.strip_plus_tags:
        address = _strip_plus_tag(address)
    domain = address.rpartition("@")[2]
    rules = list_sender_rules(session, group=group)
    for rule in rules:
        if rule.pattern == address:
            return rule
    for rule in rules:
        if rule.kind == "domain" or rule.pattern.startswith("@"):
            if rule.pattern.lstrip("@") == domain:
                return rule
    return None


def filing_for(
    session: Session, group: str, from_email: Optional[str]
) -> Filing:
    """
    Where a message from this sender belongs.

    A registered sender files under its cluster's section; an unregistered
    one waits in the unassigned state, which is where the admin's
    worklist of "who should I register?" comes from.
    """
    rule = match_sender_rule(session, group, from_email)
    if rule is None:
        return Filing(section=UNASSIGNED_SECTION)
    return Filing(
        section=rule.section,
        cluster_id=rule.cluster_id,
        pattern=rule.pattern,
        kind=rule.kind,
        rule_id=rule.id,
    )


def refile_message(
    session: Session, message: MailMessage, filing: Filing
) -> MailMessage:
    """Put one message where the rules say it belongs."""
    message.section = filing.section
    message.cluster_id = filing.cluster_id
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def refile_sender(
    session: Session, group: str, from_email: Optional[str]
) -> int:
    """
    File every message from a sender by the current rules.

    This is what happens when a sender is registered (or unregistered): the
    mail that sender wrote is put where it belongs, all of it at once.
    """
    address = (from_email or "").strip().lower()
    if not address:
        return 0
    changed = 0
    for message in _messages(session, group):
        if (message.from_email or "").lower() != address:
            continue
        if message.direction != MailDirection.INBOX.value:
            continue
        filing = filing_for(session, group, address)
        if message.section != filing.section or message.cluster_id != filing.cluster_id:
            message.section = filing.section
            message.cluster_id = filing.cluster_id
            session.add(message)
            changed += 1
    if changed:
        session.commit()
    return changed


def refile_all(session: Session, group: Optional[str] = None) -> int:
    """
    File every message in the group by the current rules.

    The button on the admin screen: after the college registers a whole
    new cluster, the mail that arrived before it is filed as well.
    """
    changed = 0
    for message in _messages(session, group):
        if message.direction != MailDirection.INBOX.value:
            continue
        filing = filing_for(session, message.group, message.from_email)
        if message.section != filing.section or message.cluster_id != filing.cluster_id:
            message.section = filing.section
            message.cluster_id = filing.cluster_id
            session.add(message)
            changed += 1
    if changed:
        session.commit()
    return changed


def unknown_senders(
    session: Session, group: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    The senders nobody registered, with how much mail each wrote.

    This is the admin's worklist: every row is a candidate for a cluster.
    The suggested section is a hint from the words in the mail - the
    college decides, not the words.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for message in _messages(session, group):
        if message.direction != MailDirection.INBOX.value:
            continue
        address = (message.from_email or "").strip().lower()
        if not address:
            continue
        if match_sender_rule(session, message.group, address) is not None:
            continue
        row = seen.get(address)
        if row is None:
            row = {
                "from_email": address,
                "from_name": message.from_name,
                "count": 0,
                "unread": 0,
                "last_seen": message.received_at,
                "suggested_section": classify(
                    message.from_name or "",
                    address,
                    message.subject or "",
                    (message.body_text or "")[:400],
                ),
            }
            seen[address] = row
        row["count"] += 1
        if message.received_at and (
            row["last_seen"] is None or message.received_at > row["last_seen"]
        ):
            row["last_seen"] = message.received_at
    rows = sorted(
        seen.values(), key=lambda row: (-int(row["count"]), str(row["from_email"]))
    )
    return rows


# --------------------------------------------------------------------------
# Messages: storage, listing, counts.
#


def store_message(
    session: Session,
    *,
    group: str,
    from_email: str,
    from_name: Optional[str] = None,
    to_email: Optional[str] = None,
    to_emails: Optional[List[str]] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    subject: Optional[str] = None,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    received_at: Optional[datetime] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    labels: Optional[List[str]] = None,
    section: Optional[str] = None,
    cluster_id: Optional[int] = None,
    thread_id: Optional[str] = None,
    intake_address: Optional[str] = None,
    message_id: Optional[str] = None,
    direction: str = MailDirection.INBOX.value,
    created_by: Optional[int] = None,
    is_quarantined: bool = False,
    auth_spf: Optional[str] = None,
    auth_dkim: Optional[str] = None,
    auth_dmarc: Optional[str] = None,
    auth_summary: Optional[str] = None,
) -> MailMessage:
    """
    File a message.

    The same message is never filed twice: the identifier is checked first,
    so a poller that runs every minute over a mailbox that does not move
    costs one row, not one row a minute.
    """
    if not from_email:
        raise ValueError("A message needs a sender.")
    if not is_group(group):
        raise ValueError(f"Unknown mail group '{group}'.")
    if received_at is None:
        received_at = _now()

    identifier = message_id or message_id_for(
        group, from_email, subject or "", received_at
    )
    existing = session.exec(
        select(MailMessage).where(MailMessage.message_id == identifier)
    ).first()
    if existing is not None:
        return existing

    # No section was asked for, so the sender decides - and a sender
    # nobody registered leaves the mail in the unassigned state, where
    # the admin's worklist finds it. The words never move it.
    if not is_storable_section(section):
        if direction == MailDirection.INBOX.value:
            filing = filing_for(session, group, from_email)
            section = filing.section
            if cluster_id is None:
                cluster_id = filing.cluster_id
        else:
            # A message of our own is not a notice from a stranger.
            section = "other"
    if thread_id is None:
        thread_id = thread_key(subject)

    message = MailMessage(
        message_id=identifier,
        group=group,
        section=section,
        cluster_id=cluster_id,
        thread_id=thread_id,
        direction=direction,
        from_email=from_email.lower(),
        from_name=from_name,
        to_email=to_email,
        to_emails=to_emails or [],
        cc_emails=cc_emails or [],
        bcc_emails=bcc_emails or [],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        snippet=_snippet(body_text or body_html),
        received_at=received_at,
        intake_address=intake_address,
        is_quarantined=is_quarantined,
        auth_spf=auth_spf,
        auth_dkim=auth_dkim,
        auth_dmarc=auth_dmarc,
        auth_summary=auth_summary,
        has_attachments=bool(attachments),
        attachments=list(attachments or []),
        labels=list(labels or []),
        created_by=created_by,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_messages(
    session: Session,
    group: Optional[str] = None,
    section: Optional[str] = None,
    cluster_id: Optional[int] = None,
    search: Optional[str] = None,
    starred: Optional[bool] = None,
    direction: Optional[str] = None,
    state: Optional[str] = None,
    page: int = 1,
    size: int = 30,
) -> Tuple[List[MailMessage], int]:
    """
    The messages, newest first.

    ``search`` looks in the sender, the subject and the body - a notice is
    found by who wrote it, what it says, or what is in it - and understands
    the operators a mail app writes (``from:``, ``section:``, ``is:unread``,
    ``has:attachment``).

    ``state`` is where in the app the message sits: ``inbox`` (the default
    pile), ``sent``, ``archived``, ``trashed`` or ``all``. Nothing in the
    trash and nothing archived is in the inbox list, exactly as a mail app
    keeps them apart.
    """
    stmt = select(MailMessage)
    if is_group(group):
        stmt = stmt.where(MailMessage.group == group)
    if is_storable_section(section):
        stmt = stmt.where(MailMessage.section == section)
    if cluster_id:
        stmt = stmt.where(MailMessage.cluster_id == cluster_id)
    if starred is not None:
        stmt = stmt.where(MailMessage.is_starred == starred)
    if state == "trashed":
        stmt = stmt.where(MailMessage.is_trashed == True)  # noqa: E712
    elif state == "archived":
        stmt = stmt.where(
            MailMessage.is_archived == True,  # noqa: E712
            MailMessage.is_trashed == False,  # noqa: E712
        )
    elif state == "sent":
        stmt = stmt.where(
            MailMessage.direction == MailDirection.SENT.value,
            MailMessage.is_trashed == False,  # noqa: E712
        )
    elif state == "all":
        pass
    else:
        stmt = stmt.where(
            MailMessage.is_trashed == False,  # noqa: E712
            MailMessage.is_archived == False,  # noqa: E712
            MailMessage.direction == MailDirection.INBOX.value,
        )
    if direction in ("inbox", MailDirection.SENT.value):
        stmt = stmt.where(MailMessage.direction == direction)

    filters = parse_search(search)
    if filters["from"]:
        stmt = stmt.where(
            func.lower(MailMessage.from_email).like(f"%{filters['from']}%")
        )
    if filters["to"]:
        stmt = stmt.where(func.lower(MailMessage.to_email).like(f"%{filters['to']}%"))
    if filters["section"]:
        wanted = filters["section"]
        if is_storable_section(wanted):
            stmt = stmt.where(MailMessage.section == wanted)
    if filters["label"]:
        needle = f"%{filters['label']}%"
        stmt = stmt.where(
            or_(
                func.lower(MailMessage.subject).like(needle),
                func.lower(MailMessage.body_text).like(needle),
            )
        )
    if filters["unread"] is not None:
        stmt = stmt.where(MailMessage.is_read != filters["unread"])
    if filters["starred"] is not None:
        stmt = stmt.where(MailMessage.is_starred == filters["starred"])
    if filters["has_attachment"] is not None:
        stmt = stmt.where(MailMessage.has_attachments == filters["has_attachment"])

    term = " ".join(filters["words"]).strip()
    if term:
        like = f"%{term.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(MailMessage.subject).like(like),
                func.lower(MailMessage.from_email).like(like),
                func.lower(MailMessage.from_name).like(like),
                func.lower(MailMessage.body_text).like(like),
                func.lower(MailMessage.snippet).like(like),
            )
        )

    rows = session.exec(stmt).all()
    total = len(rows)
    rows.sort(
        key=lambda m: (
            m.received_at is None,
            -(m.received_at.timestamp() if m.received_at else 0),
        )
    )
    page = max(1, page)
    size = max(1, min(size, 100))
    start = (page - 1) * size
    return rows[start : start + size], total


def get_message(session: Session, message_id: int) -> Optional[MailMessage]:
    """One message by its id."""
    return session.get(MailMessage, message_id)


def mark_read(session: Session, message: MailMessage, read: bool = True) -> MailMessage:
    """Mark a message read or unread."""
    message.is_read = read
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def toggle_star(session: Session, message: MailMessage) -> MailMessage:
    """Star a message, or unstar it if it already was."""
    message.is_starred = not message.is_starred
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def section_counts(session: Session, group: Optional[str] = None) -> Dict[str, int]:
    """How many messages each section holds."""
    counts = {section: 0 for section in _section_ids()}
    for message in _messages(session, group):
        if message.section in counts:
            counts[message.section] += 1
    return counts


def unread_counts(session: Session, group: Optional[str] = None) -> Dict[str, int]:
    """How many unread messages each section holds."""
    counts = {section: 0 for section in _section_ids()}
    for message in _messages(session, group):
        if message.is_read or message.section not in counts:
            continue
        counts[message.section] += 1
    return counts


def starred_count(session: Session, group: Optional[str] = None) -> int:
    """How many starred messages there are."""
    return sum(1 for message in _messages(session, group) if message.is_starred)


def cluster_message_count(
    session: Session, cluster_id: int, group: Optional[str] = None
) -> int:
    """How much mail a cluster has filed."""
    return sum(
        1
        for message in _messages(session, group)
        if message.cluster_id == cluster_id
    )


# --------------------------------------------------------------------------
# Search.
#


def parse_search(query: Optional[str]) -> Dict[str, Any]:
    """
    Split a search box's words into filters and free text.

    ``from:`` a sender, ``section:`` a label, ``to:`` a recipient,
    ``is:unread`` / ``is:read`` / ``is:starred``, ``has:attachment``,
    ``label:`` a mail label. Everything else is the words to look for.
    """
    filters: Dict[str, Any] = {
        "from": None,
        "to": None,
        "section": None,
        "label": None,
        "unread": None,
        "starred": None,
        "has_attachment": None,
        "words": [],
    }
    for token in (query or "").split():
        key, _, value = token.partition(":")
        value = value.strip().lower()
        if not value and key.lower() in ("is", "has"):
            continue
        key = key.lower()
        if key == "from":
            filters["from"] = value
        elif key == "to":
            filters["to"] = value
        elif key in ("section", "label", "in"):
            filters["section"] = value
        elif key == "is":
            if value in ("unread", "read"):
                filters["unread"] = value == "unread"
            elif value in ("starred", "unstarred"):
                filters["starred"] = value == "starred"
        elif key == "has":
            if value in ("attachment", "attachments", "file", "files"):
                filters["has_attachment"] = True
            elif value in ("noattachment", "noattachments"):
                filters["has_attachment"] = False
        else:
            filters["words"].append(token)
    return filters


# --------------------------------------------------------------------------
# Helpers.
#


def _section_ids() -> Tuple[str, ...]:
    from features.mail.sections import SECTION_IDS

    # The unassigned state counts as a section here: the app shows how much
    # mail is waiting for a sender to be registered.
    return tuple(SECTION_IDS) + (UNASSIGNED_SECTION,)


def _messages(session: Session, group: Optional[str] = None) -> List[MailMessage]:
    stmt = select(MailMessage)
    if is_group(group):
        stmt = stmt.where(MailMessage.group == group)
    return list(session.exec(stmt).all())
