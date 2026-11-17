from typing import Optional
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from fastapi import HTTPException, status

from app.models.contact import Contact, ContactCreate, ContactUpdate, ContactGroup, ContactGroupCreate


async def list_contacts(
    session: AsyncSession,
    user_id: str,
    q: Optional[str] = None,
    group_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Contact]:
    stmt = select(Contact).where(Contact.user_id == user_id)
    if q:
        stmt = stmt.where(
            (Contact.name.ilike(f"%{q}%")) | (Contact.email.ilike(f"%{q}%"))
        )
    if group_id:
        stmt = stmt.where(Contact.group_id == group_id)
    stmt = stmt.order_by(Contact.name.nullslast(), Contact.email).limit(limit).offset(offset)
    result = await session.exec(stmt)
    return result.all()


async def get_contact(
    session: AsyncSession,
    user_id: str,
    contact_id: UUID,
) -> Contact:
    result = await session.exec(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
    )
    contact = result.first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


async def create_contact(
    session: AsyncSession,
    user_id: str,
    data: ContactCreate,
) -> Contact:
    contact = Contact(user_id=user_id, **data.model_dump())
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact


async def update_contact(
    session: AsyncSession,
    user_id: str,
    contact_id: UUID,
    data: ContactUpdate,
) -> Contact:
    contact = await get_contact(session, user_id, contact_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact


async def delete_contact(
    session: AsyncSession,
    user_id: str,
    contact_id: UUID,
) -> None:
    contact = await get_contact(session, user_id, contact_id)
    await session.delete(contact)
    await session.commit()


async def autocomplete_contacts(
    session: AsyncSession,
    user_id: str,
    q: str,
    limit: int = 10,
) -> list[Contact]:
    result = await session.exec(
        select(Contact).where(
            Contact.user_id == user_id,
            (Contact.name.ilike(f"%{q}%")) | (Contact.email.ilike(f"%{q}%")),
        ).limit(limit)
    )
    return result.all()


async def list_contact_groups(
    session: AsyncSession,
    user_id: str,
) -> list[ContactGroup]:
    result = await session.exec(
        select(ContactGroup).where(ContactGroup.user_id == user_id).order_by(ContactGroup.name)
    )
    return result.all()


async def create_contact_group(
    session: AsyncSession,
    user_id: str,
    data: ContactGroupCreate,
) -> ContactGroup:
    group = ContactGroup(user_id=user_id, **data.model_dump())
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group
