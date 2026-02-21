from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey, Enum as PgEnum
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import GenderEnum


class Guest(Base):
    __tablename__ = "Guest"

    id      = Column(BigInteger, primary_key=True, autoincrement=True)
    name    = Column(String,  nullable=False)
    gender  = Column(PgEnum(GenderEnum, name="genderenum"), nullable=True)
    age     = Column(Integer, nullable=True)
    user_id = Column(BigInteger, ForeignKey("app_user.id"), nullable=False)

    # Each guest belongs to a user — user manages their own guest list
    user = relationship("User", back_populates="guests")
