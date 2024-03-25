import io
from numpy import asarray
from db import getSession, User, Patient, Image
from werkzeug.datastructures import FileStorage
import boto3
import uuid
from sqlalchemy.orm import Query
from botocore.client import Config
from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog, DatasetCatalog
from PIL import Image as Image2
from skimage.measure import regionprops, label


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


def downloadImg(img: Image):
    s3 = boto3.client("s3")
    buf = io.BytesIO()
    s3.download_fileobj("comp413", img.imageUrl, buf)
    return asarray(Image2.open(buf))


def getLesions(image_id: int):
    img = getImage(image_id)
    if img == None:
        return None

    # download image somehow
    im = downloadImg(img)

    predictor = get_lesion_predictor()
    outputs = predictor(im)

    # Convert the predicted mask to a binary mask
    mask = outputs["instances"].pred_masks.to("cpu").numpy().astype(bool)
    class_labels = outputs["instances"].pred_classes.to("cpu").numpy()

    # Use skimage.measure.regionprops to calculate object parameters
    labeled_mask = label(mask)
    props = regionprops(labeled_mask)

    # Write the object-level information to the CSV file
    for i, prop in enumerate(props):
        object_number = i + 1  # Object number starts from 1
        area = prop.area
        centroid = prop.centroid
        bounding_box = prop.bbox

        # Check if the corresponding class label exists
        if i < len(class_labels):
            class_label = class_labels[i]
            class_name = class_label
            # class_name = train_metadata.thing_classes[class_label]
        else:
            # If class label is not available (should not happen), use 'Unknown' as class name
            class_name = "Unknown"

        # Write the object-level information to the CSV file
        print(class_name, object_number, area, centroid, bounding_box)
    return "Yay!"


def get_lesion_predictor():
    cfg = get_cfg()
    cfg.merge_from_file("./models/detection_model/config.yaml")
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.2
    cfg.MODEL.WEIGHTS = "./models/detection_model/model.pth"
    return DefaultPredictor(cfg)


def get_segmentation_predictor():
    cfg = get_cfg()
    cfg.merge_from_file("./models/segmentation_model/config.yaml")
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.2
    cfg.MODEL.WEIGHTS = "./models/segmentation_model/model.pth"
    return DefaultPredictor(cfg)
