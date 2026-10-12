"""Create a test user directly in the database, bypassing email verification."""
import sys
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend")
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app")

from sqlmodel import Session, SQLModel, create_engine, select
from passlib.hash import sha256_crypt
from datetime import datetime

engine = create_engine("postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot")

with Session(engine) as session:
    from models import User, UserProfile

    # Delete existing test user and profile
    existing = session.exec(select(User).where(User.email == "test@iiitdmj.ac.in")).first()
    if existing:
        session.delete(existing)
        session.commit()
        print("Deleted existing test user")

    # Also clean up any orphaned profiles
    orphaned = session.exec(select(UserProfile).where(UserProfile.user_id == 1)).first()
    if orphaned:
        session.delete(orphaned)
        session.commit()
        print("Deleted orphaned profile")

    # Create user
    password_hash = sha256_crypt.hash("TestPass123!")
    now = datetime.utcnow()

    user = User(
        email="test@iiitdmj.ac.in",
        password_hash=password_hash,
        full_name="Test User",
        username="testuser",
        roll_number="21BCE1234",
        is_email_verified=True,
        role="student",
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    print(f"Created user: id={user.id}, email={user.email}")

    # Create profile
    profile = UserProfile(
        user_id=user.id,
        first_name="Test",
        last_name="User",
        gender="Male",
        programme="BTech",
        semester=3,
        branch="CSE A",
        elective_codes=[],
    )
    session.add(profile)
    session.commit()
    print(f"Created profile for user {user.id}")
    print(f"Login with: username=testuser, password=TestPass123!")
