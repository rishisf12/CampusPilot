from sqlmodel import Session, select, create_engine
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import User, UserProfile
    
    user = session.exec(select(User).where(User.username == 'testuser')).first()
    if not user:
        print("Test user not found!")
        exit(1)
    
    # Get or create profile
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    if profile:
        print(f"Updating profile: branch={profile.branch} -> CSE, semester={profile.semester} -> 5")
        profile.branch = "CSE"
        profile.semester = 5
        session.add(profile)
    else:
        print("Creating new profile")
        profile = UserProfile(
            user_id=user.id,
            first_name="Test",
            last_name="User",
            gender="Other",
            programme="BTech",
            semester=5,
            branch="CSE",
            elective_codes=[],
        )
        session.add(profile)
    
    session.commit()
    print("Done!")