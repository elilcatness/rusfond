from sqlalchemy import Column, Integer, String, Boolean

from src.db_session import SqlAlchemyBase


class User(SqlAlchemyBase):
    __tablename__ = 'users'

    username = Column(String, primary_key=True, unique=True)
    id = Column(Integer, unique=True)
    is_premium = Column(Boolean, default=False)
    invite_link = Column(String, nullable=True)