#!/usr/bin/env python3
"""
Scaffold a new feature module with all boilerplate:
- models.py with extend_existing=True
- routes.py with full CRUD + auth matrix tests
- service.py with business logic
- __init__.py
- test file with auth matrix (401/403/200) + behavior tests
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

TEMPLATE_MODELS = '''"""{{feature_name}} models."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class {{ModelName}}(SQLModel, table=True):
    __tablename__ = "{{table_name}}"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    is_active: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
'''

TEMPLATE_ROUTES = '''"""{{feature_name}} routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from features.{{feature_dir}} import service

router = APIRouter(prefix="/admin/{{feature_dir}}", tags=["Admin - {{FeatureTitle}}"])


class {{ModelName}}Create(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class {{ModelName}}Update(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class {{ModelName}}Response(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_by: Optional[int]
    created_at: str
    updated_at: str


@router.get("")
def admin_list_{{feature_dir}}(
    page: int = 1,
    size: int = 20,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_{{feature_dir}}(session, page, size)
    return {"total": total, "page": page, "size": size, "{{feature_dir}}": [service.to_public(r) for r in rows]}


@router.post("", response_model=dict, status_code=201)
def admin_create_{{feature_dir}}(
    body: {{ModelName}}Create,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    item = service.create_{{feature_dir}}(session, body, admin.id)
    return service.to_public(item)


@router.get("/{{{feature_dir}_id}}")
def admin_get_{{feature_dir}}(
    {{feature_dir}_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    item = service.get_{{feature_dir}}(session, {{feature_dir}_id})
    if not item:
        raise HTTPException(status_code=404, detail="{{FeatureTitle}} not found")
    return service.to_public(item)


@router.patch("/{{{feature_dir}_id}}")
def admin_update_{{feature_dir}}(
    {{feature_dir}_id: int,
    body: {{ModelName}}Update,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    item = service.update_{{feature_dir}}(session, {{feature_dir}_id}, body, admin.id)
    if not item:
        raise HTTPException(status_code=404, detail="{{FeatureTitle}} not found")
    return service.to_public(item)


@router.delete("/{{{feature_dir}_id}}", status_code=204)
def admin_delete_{{feature_dir}}(
    {{feature_dir}_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    if not service.delete_{{feature_dir}}(session, {{feature_dir}_id}):
        raise HTTPException(status_code=404, detail="{{FeatureTitle}} not found")
'''

TEMPLATE_SERVICE = '''"""{{feature_name}} service."""
from __future__ import annotations
from typing import Optional, List
from sqlmodel import Session, select
from sqlalchemy import desc

from features.{{feature_dir}}.models import {{ModelName}}


def list_{{feature_dir}}(
    session: Session,
    page: int = 1,
    size: int = 20,
) -> tuple[list, int]:
    from models import {{ModelName}}
    stmt = select({{ModelName}})
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(desc({{ModelName}}.created_at))
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def create_{{feature_dir}}(session, body, created_by: int):
    from models import {{ModelName}}
    item = {{ModelName}}(
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        created_by=created_by,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_{{feature_dir}}(session, item_id: int):
    from models import {{ModelName}}
    return session.get({{ModelName}}, item_id)


def update_{{feature_dir}}(session, item_id: int, body, updated_by: int):
    from models import {{ModelName}}
    item = session.get({{ModelName}}, item_id)
    if not item:
        return None
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    item.updated_at = __import__('datetime').datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_{{feature_dir}}(session, item_id: int) -> bool:
    from models import {{ModelName}}
    item = session.get({{ModelName}}, item_id)
    if not item:
        return False
    session.delete(item)
    session.commit()
    return True


def to_public(item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "is_active": item.is_active,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
'''

TEMPLATE_TEST = '''"""Tests for {{feature_name}}."""
import pytest
from sqlmodel import Session
from models import User, UserRole
from features.auth.routes import create_access_token
from fastapi.testclient import TestClient
from main import app


def test_{{feature_dir}}_auth_matrix(require_postgres):
    from fastapi.testclient import TestClient
    from main import app
    from core.database import engine
    from models import User, UserRole
    from features.auth.routes import create_access_token

    with Session(engine) as s:
        user = s.exec(User.select().where(User.username == "testuser")).first()
        if not user:
            user = User(
                email="test@iiitdmj.ac.in", password_hash="x",
                full_name="Test User", username="testuser",
                is_email_verified=True, role=UserRole.STUDENT,
            )
            s.add(user)
            s.commit()
            s.refresh(user)

        admin = s.exec(User.select().where(User.role == UserRole.ADMIN)).first()
        admin_token = create_access_token(admin.id, admin.username) if admin else None
        user_token = create_access_token(user.id, user.username)

    client = TestClient(app)

    # 401 - No auth
    r = client.get("/admin/{{feature_dir}}")
    assert r.status_code == 401

    # 403 - Non-admin
    r = client.get("/admin/{{feature_dir}}", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403

    # 200 - Admin
    r = client.get("/admin/{{feature_dir}}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200


def test_{{feature_dir}}_crud(require_postgres):
    from core.database import engine
    from features.{{feature_dir}} import service
    from models import {{ModelName}}

    with Session(engine) as s:
        # Create
        item = service.create_{{feature_dir}}(s, type('obj', (), {
            'name': 'Test Item',
            'description': 'Test description',
            'is_active': True
        })(), admin_id=1)
        assert item.name == "Test Item"
        assert item.is_active is True

        # List
        rows, total = service.list_{{feature_dir}}(s, 1, 10)
        assert total >= 1

        # Get
        item = service.get_{{feature_dir}}(s, item.id)
        assert item.name == "Test Item"

        # Update
        updated = service.update_{{feature_dir}}(s, item.id, type('obj', (), {
            'name': 'Updated Name'
        })(), admin_id=1)
        assert updated.name == "Updated Name"

        # Delete
        assert service.delete_{{feature_dir}}(s, item.id) is True
        assert service.get_{{feature_dir}}(s, item.id) is None
'''

def scaffold_feature(name: str, force: bool = False):
    """Scaffold a new feature module."""
    feature_dir = name.lower().replace('-', '_').replace(' ', '_')
    model_name = ''.join(word.capitalize() for word in name.split('_'))
    feature_title = ' '.join(word.capitalize() for word in name.split('_'))
    table_name = feature_dir

    base_path = Path(__file__).parent.parent / "backend" / "app" / "features" / feature_dir
    
    if base_path.exists() and not force:
        print(f"Directory {base_path} already exists. Use --force to overwrite.")
        return False

    base_path.mkdir(parents=True, exist_ok=True)

    # Create files
    files = {
        "models.py": TEMPLATE_MODELS
            .replace("{{feature_name}}", name)
            .replace("{{ModelName}}", model_name)
            .replace("{{feature_dir}}", feature_dir)
            .replace("{{table_name}}", table_name),
        "routes.py": TEMPLATE_ROUTES
            .replace("{{feature_name}}", name)
            .replace("{{ModelName}}", model_name)
            .replace("{{feature_dir}}", feature_dir)
            .replace("{{FeatureTitle}}", feature_title),
        "service.py": TEMPLATE_SERVICE
            .replace("{{feature_name}}", name)
            .replace("{{ModelName}}", model_name)
            .replace("{{feature_dir}}", feature_dir),
        "__init__.py": f'"""{{feature_title}} feature package."""\nfrom . import routes  # noqa: F401\n',
        f"test_{feature_dir}.py": TEMPLATE_TEST
            .replace("{{feature_name}}", name)
            .replace("{{feature_dir}}", feature_dir)
            .replace("{{ModelName}}", model_name)
            .replace("{{FeatureTitle}}", feature_title),
    }

    for filename, content in files.items():
        (base_path / filename).write_text(content, encoding='utf-8')
        print(f"Created {base_path / filename}")

    # Add to models.py
    models_path = Path(__file__).parent.parent / "backend" / "app" / "models.py"
    models_content = models_path.read_text(encoding='utf-8')
    if f"class {model_name}" not in models_content:
        import_text = f"\n\nclass {model_name}(SQLModel, table=True):\n    __tablename__ = \"{table_name}\"\n    __table_args__ = {{\"schema\": \"core\", \"extend_existing\": True}}\n\n    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))\n    name: str = Field(max_length=200, index=True)\n    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))\n    is_active: bool = Field(default=True)\n    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey(\"core.user.id\")))\n    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))\n    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))\n"
        # Find end of file and append
        models_path.write_text(models_content + import_text, encoding='utf-8')
        print(f"Added {model_name} to models.py")

    print(f"\n✅ Feature '{name}' scaffolded successfully!")
    print(f"📁 Location: {base_path}")
    print(f"🔧 Next steps:")
    print(f"   1. Run alembic revision --autogenerate -m 'add {table_name}'")
    print(f"   2. Run alembic upgrade heads")
    print(f"   3. Add routes to main.py if needed")
    print(f"   4. Run pytest tests/test_{feature_dir}.py")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold a new feature module")
    parser.add_argument("name", help="Feature name (e.g., 'user-profile', 'content-moderation')")
    parser.add_argument("--force", action="store_true", help="Overwrite existing")
    args = parser.parse_args()

    scaffold_feature(args.name, args.force)