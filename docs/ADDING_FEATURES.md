# Adding a New Feature to CampusPilot Admin Platform

This guide walks through adding a new feature module to the CampusPilot Admin Platform, from backend to frontend.

---

## Quick Start (Automated Scaffolding)

### Backend
```bash
python backend/app/scripts/scaffold_feature.py "my-feature"
```

### Frontend
```bash
node scaffold-feature.js my-feature
```

---

## Manual Step-by-Step

### 1. Backend: Create Feature Module

```
backend/app/features/my_feature/
├── __init__.py
├── models.py
├── service.py
├── routes.py
└── tests/
    └── test_my_feature.py
```

### 2. Define Models (`models.py`)

```python
"""My Feature models."""
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Identity, Integer, ForeignKey
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


class MyFeature(SQLModel, table=True):
    __tablename__ = "my_feature"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(postgresql.TEXT))
    is_active: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("core.user.id")))
    created_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column(postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()))
```

### 3. Add to models.py

Append to `backend/app/models.py`:

```python
class MyFeature(SQLModel, table=True):
    __tablename__ = "my_feature"
    __table_args__ = {"schema": "core", "extend_existing": True}
    # ... fields as above
```

### 4. Create Migration

```bash
cd backend
alembic revision --autogenerate -m "add my_feature table"
alembic upgrade heads
```

### 5. Service Layer (`service.py`)

```python
"""My Feature service."""
from __future__ import annotations
from typing import Optional, List
from sqlmodel import Session, select
from sqlalchemy import desc

from features.my_feature.models import MyFeature


def list_my_feature(session, page: int = 1, size: int = 20) -> tuple[list, int]:
    stmt = select(MyFeature)
    total = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.order_by(desc(MyFeature.created_at))
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return rows, total


def create_my_feature(session, body, created_by: int):
    item = MyFeature(
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        created_by=created_by,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_my_feature(session, item_id: int):
    return session.get(MyFeature, item_id)


def update_my_feature(session, item_id: int, body, updated_by: int):
    item = session.get(MyFeature, item_id)
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


def delete_my_feature(session, item_id: int) -> bool:
    item = session.get(MyFeature, item_id)
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
```

### 6. Create Routes (`routes.py`)

```python
"""My Feature routes."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from core.deps import get_current_admin
from features.my_feature import service

router = APIRouter(prefix="/admin/my-feature", tags=["Admin - My Feature"])


class MyFeatureCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class MyFeatureUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def admin_list_my_feature(
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    page = max(1, page)
    size = max(1, min(size, 100))
    rows, total = service.list_my_feature(session, page, size)
    return {"total": total, "page": page, "size": size, "items": [service.to_public(r) for r in rows]}


@router.post("", status_code=201)
def admin_create_my_feature(
    body: MyFeatureCreate,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    item = service.create_my_feature(session, body, admin.id)
    return {"id": item.id, "name": item.name, "created_at": item.created_at.isoformat()}


@router.get("/{item_id}")
def admin_get_my_feature(
    item_id: int,
    session: Session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    item = session.get(MyFeature, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item.id, "name": item.name, "description": item.description, "is_active": item.is_active}


@router.patch("/{item_id}")
def admin_update_my_feature(
    item_id: int,
    body: MyFeatureUpdate,
    session = Depends(get_session),
    admin = Depends(get_current_admin),
):
    from features.my_feature import service
    item = service.update_my_feature(session, item_id, body, admin.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item.id, "name": item.name, "updated_at": item.updated_at.isoformat()}


@router.delete("/{item_id}", status_code=204)
def admin_delete_my_feature(
    item_id: int,
    session = Depends(get_session),
    _ = Depends(get_current_admin),
):
    from features.my_feature import service
    if not service.delete_my_feature(session, item_id):
        raise HTTPException(status_code=404, detail="Item not found")
```

### 7. Add to `__init__.py`

```python
"""My Feature feature package."""
from . import routes  # noqa: F401
```

### 7. Register in `main.py`

```python
from features.my_feature import routes as my_feature_routes
app.include_router(my_feature_routes.router, prefix="/admin", tags=["Admin - My Feature"])
```

### 8. Create Migration

```bash
cd backend
alembic revision --autogenerate -m "add my_feature table"
alembic upgrade heads
```

### 9. Write Tests (`tests/test_my_feature.py`)

```python
"""Tests for My Feature."""
import pytest
from sqlmodel import Session
from models import User, UserRole
from features.auth.routes import create_access_token
from fastapi.testclient import TestClient
from main import app


def test_my_feature_auth_matrix(require_postgres):
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

        admin_user = s.exec(User.select().where(User.role == UserRole.ADMIN)).first()
        admin_token = create_access_token(admin_user.id, admin_user.username) if admin_user else None
        user_token = create_access_token(user.id, user.username)

    client = TestClient(app)

    # 401 - No auth
    r = client.get("/admin/my-feature")
    assert r.status_code == 401

    # 403 - Non-admin
    r = client.get("/admin/my-feature", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403

    # 200 - Admin
    r = client.get("/admin/my-feature", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200


def test_my_feature_crud(require_postgres):
    from core.database import engine
    from features.my_feature import service

    with Session(engine) as s:
        item = service.create_my_feature(s, type('obj', (), {
            'name': 'Test Item',
            'description': 'Test description',
            'is_active': True
        })(), admin_id=1)
        assert item.name == "Test Item"
        assert item.is_active is True

        rows, total = service.list_my_feature(s, 1, 10)
        assert total >= 1

        item = service.get_my_feature(s, item.id)
        assert item.name == "Test Item"

        updated = service.update_my_feature(s, item.id, type('obj', (), {
            'name': 'Updated Name'
        })(), admin_id=1)
        assert updated.name == "Updated Name"

        assert service.delete_my_feature(s, item.id) is True
        assert service.get_my_feature(s, item.id) is None
```

---

## Frontend: Add Admin Panel Tab

### 1. Create Component (`Analytics.tsx`)

```tsx
import { useEffect, useState } from 'react';
import { adminApi } from '@/api';
import { Card, Badge, Input, Button, Tabs, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function MyFeature({ onError }: { onError?: (m: string) => void }) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.myFeature();
      setData(data.items || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>Loading…</div>;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">My Feature</h2>
      <Card>
        <h3 className="text-lg font-semibold mb-4">Items</h3>
        {data.map(item => (
          <div key={item.id} className="p-3 border-b">
            <p className="font-medium">{item.name}</p>
            <p className="text-sm text-gray-500">{item.description || '—'}</p>
          </div>
        ))}
      </Card>
    </div>
  );
}
```

### 2. Add to AdminPanel.tsx

```tsx
const MyFeature = lazy(() => import('./MyFeature').then(m => ({ default: m.default })));

// In SUB_TABS:
{ id: 'my-feature', label: 'My Feature', icon: <MyIcon size={16} strokeWidth={2} /> }

// In render:
{tab === 'my-feature' && <MyFeature onError={(msg) => setError(msg)} />}
```

### 3. Add to `api.ts`

```typescript
// In adminApi:
myFeature: () => request<{ total: number; page: number; size: number; items: MyFeatureItem[] }>('/admin/my-feature'),
```

---

## Testing Checklist

- [ ] Backend tests pass: `pytest tests/test_my_feature.py -v`
- [ ] Frontend builds: `npm run build`
- [ ] TypeScript passes: `npx tsc --noEmit`
- [ ] Lint passes: `npm run lint`
- [ ] Auth matrix tests pass (401/403/200)
- [ ] CRUD operations work end-to-end
- [ ] Migration applies cleanly: `alembic upgrade heads`

---

## Deployment Checklist

- [ ] Run `alembic upgrade heads` on staging
- [ ] Run `pytest tests/test_my_feature.py -v` on staging
- [ ] Verify frontend builds: `npm run build`
- [ ] Deploy via CI/CD
- [ ] Monitor `/health/ready` after deploy
- [ ] Check error rates in Admin Panel → Errors

---

## Best Practices

1. **Always use `extend_existing=True`** in `__table_args__` for models
2. **Use `sa.func.now()`** for server-side timestamps
3. **Add `get_current_admin` dependency** to all admin routes
4. **Write auth matrix tests** (401/403/200)
5. **Use `get_current_admin`** for admin-only endpoints
6. **Log audit events** for all mutations
7. **Use transactions** for multi-step operations
8. **Add indexes** for frequently queried columns