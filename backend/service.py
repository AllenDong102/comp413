from db import init, getSession, User, Patient, Image
from werkzeug.datastructures import FileStorage

def createUser(name: str, role: str):
    user = User(name=name, role=role)
    with getSession() as session:
        session.add(user)
    return user.id


def createPatient(name: str, owner_id: int):
    patient = Patient(name=name, owner_id=owner_id)
    with getSession() as session:
        session.add(patient)
    return patient.id


def createImage(url: str, patient_id: int):
    image = Image(imageUrl=url, patient_id=patient_id)
    with getSession() as session:
        session.add(image)
    return image.id

def uploadImage(file: FileStorage):
    file.
