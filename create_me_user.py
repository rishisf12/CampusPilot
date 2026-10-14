from sqlmodel import Session, select, create_engine
from passlib.hash import sha256_crypt
from datetime import datetime
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from app.models import User, UserProfile
    
    # Check if ME test user exists
    existing = session.exec(select(User).where(User.username == 'metest')).first()
    if existing:
        print('ME test user already exists')
    else:
        password_hash = sha256_crypt.hash('metest123')
        user = User(
            email='metest@iiitdmj.ac.in',
            password_hash=password_hash,
            full_name='ME Test User',
            username='metest',
            roll_number='23BME001',
            is_email_verified=True,
            role='student',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        profile = UserProfile(
            user_id=user.id,
            first_name='ME Test',
            last_name='User',
            gender='Other',
            programme='BTech',
            semester=5,
            branch='ME',
            elective_codes=[],
        )
        session.add(profile)
        session.commit()
        print('ME test user created: metest / metest123')