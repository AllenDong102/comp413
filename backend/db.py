import logging
from sqlalchemy import create_engine, String, ForeignKey, Identity
from sqlalchemy.orm import DeclarativeBase, Session, Mapped, mapped_column, relationship
from typing import List
import os

connection_string = (
    "mysql+mysqlconnector://iqe54l4f5bgjh1cboyl2:"
    + os.getenv("DB_PASSWORD")
    + "@aws.connect.psdb.cloud:3306/comp413"
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
        back_populates="patient", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Patient(id={self.id}, name={self.name}, owner{self.owner})"


class Image(Base):
    __tablename__ = "image"

    id: Mapped[int] = mapped_column(primary_key=True)
    imageUrl: Mapped[String] = mapped_column(String(64))
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
