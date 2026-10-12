from sqlmodel import Session, select, create_engine
from passlib.hash import sha256_crypt
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import User
    user = session.exec(select(User).where(User.username == 'testuser')).first()
    if user:
        print(f'User: {user.username}')
        print(f'Email: {user.email}')
        print(f'Hash: {user.password_hash}')
        print('Test testpass123:', sha256_crypt.verify("testpass123", user.password_hash))
        print('Test test:', sha256_crypt.verify("test", user.password_hash))
        print('Test test123:', sha256_crypt.verify("test123", user.password_hash))
        print('Test password:', sha256_crypt.verify("password", user.password_hash))