import logging
from sqlalchemy import create_engine, String, ForeignKey, Identity, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Session, Mapped, mapped_column, relationship
from typing import List
from dotenv import load_dotenv
import os

load_dotenv()
connection_string = (
    "postgresql+psycopg2://postgres.ncqjhzqhntwmwftyfmkz:"
    + os.getenv("DB_PASSWORD")
    + "@aws-0-us-west-1.pooler.supabase.com:5432/postgres"
)
engine = create_engine(connection_string, echo=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))
    googleId: Mapped[str] = mapped_column(String(50))
    id: Mapped[int] = mapped_column(primary_key=True)
    patients: Mapped[List["Patient"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", lazy="joined"
    )


class Patient(Base):
    __tablename__ = "patients"

    name: Mapped[str] = mapped_column(String(50))
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="patients")

    images: Mapped[List["Image"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", lazy="joined"
    )

    def __repr__(self):
        return f"Patient(id={self.id}, name={self.name}, owner{self.owner})"


class Image(Base):
    __tablename__ = "image"

    id: Mapped[int] = mapped_column(primary_key=True)
    imageUrl: Mapped[String] = mapped_column(String(1000))
    timestamp: Mapped[DateTime] = mapped_column(DateTime(), server_default=func.now())
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))

    patient: Mapped["Patient"] = relationship(back_populates="images")

    def __repr__(self):
        return f"Image(id={self.id}, url={self.imageUrl}, patient={self.patient})"


def getSession():
    s = Session(engine)
    s.expire_on_commit = False
    return s


def init():
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
