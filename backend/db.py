from sqlalchemy import create_engine, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Session, Mapped, mapped_column, relationship
from typing import List

connection_string = "mysql+mysqlconnector://s1ww0uev97privpxy1qm:pscale_pw_EiYRYrmtibyJLrmgp0Uf6PKUupkEUOxy9LlNi08Yud0@aws.connect.psdb.cloud:3306/comp413"
engine = create_engine(connection_string, echo=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))
    id: Mapped[int] = mapped_column(primary_key=True)
    patients: Mapped[List["Patient"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
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
    imageUrl: Mapped[String] = mapped_column(String())
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))

    patient: Mapped["Patient"] = relationship(back_populates="images")

    def __repr__(self):
        return f"Image(id={self.id}, url={self.imageUrl}, patient={self.patient})"


def getSession():
    return Session(engine)


def init():
    Base.metadata.create_all(engine)
