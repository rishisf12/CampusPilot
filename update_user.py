from sqlmodel import Session, select, create_engine
from passlib.hash import sha256_crypt
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import User
    user = session.exec(select(User).where(User.username == 'testuser')).first()
    if user:
        # Set password to "test123"
        user.password_hash = sha256_crypt.hash("test123")
        session.add(user)
        session.commit()
        print("Password updated to 'test123'")
        print("Verify:", sha256_crypt.verify("test123", user.password_hash))