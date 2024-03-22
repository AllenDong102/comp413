from db import getSession, User, Patient, Image
from werkzeug.datastructures import FileStorage
import boto3
import uuid
from sqlalchemy.orm import Query
from botocore.client import Config


def createUser(name: str, role: str, googleId: str):
    with getSession() as session:
        session.expire_on_commit = False
        user = User(name=name, role=role, googleId=googleId)
        session.add(user)
        session.commit()
        return user


def createPatient(name: str, owner_id: int):
    patient = Patient(name=name, owner_id=owner_id)
    with getSession() as session:
        session.add(patient)
        session.commit()
        return patient


def createImage(url: str, patient_id: int):
    image = Image(imageUrl=url, patient_id=patient_id)
    with getSession() as session:
        session.add(image)
        session.commit()
        return image


def getUser(id: int):
    with getSession() as session:
        return session.get(User, id)


def getUserGoogle(googleId: str):
    with getSession() as session:
        return session.query(User).filter(User.googleId == googleId).one_or_none()


def getPatient(id: int):
    with getSession() as session:
        return session.get(Patient, id)


def getImage(id: int):
    with getSession() as session:
        return session.get(Image, id)


def deleteUser(id: int):
    with getSession() as session:
        session.delete(User, id)
        session.commit()


def deletePatient(id: int):
    with getSession() as session:
        session.delete(Patient, id)
        session.commit()


def deleteImage(id: int):
    with getSession() as session:
        session.delete(Image, id)
        session.commit()


def uploadImage(file: FileStorage):
    s3 = boto3.resource("s3")
    bucket = s3.Bucket("comp413")
    name = str(uuid.uuid4())
    obj = bucket.Object(name)
    obj.put(Body=file.stream)
    obj.wait_until_exists()

    return name


def getImageUrl(name: str):
    s3_client = boto3.client(
        "s3", config=Config(signature_version="s3v4", region_name="us-east-2")
    )
    url = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": "comp413", "Key": name}, ExpiresIn=3600
    )
    return url


def createAndUploadImage(file: FileStorage, patient_id: int):
    key = uploadImage(file)
    return createImage(key, patient_id)
