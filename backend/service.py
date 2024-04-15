import io
import platform
from numpy import asarray, float64
import numpy as np
import pandas as pd
import ot
import scipy
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
from typing import List


class DetectedObject:
    object_number: int
    area: float64
    centroid: tuple[float]
    bounding_box: tuple[int]
    class_tag: str

    def __init__(self, object_number: int, area, centroid, bounding_box, class_tag):
        self.object_number = object_number
        self.area = area
        self.centroid = (centroid[1], centroid[2])
        self.bounding_box = (
            bounding_box[1],
            bounding_box[2],
            bounding_box[4],
            bounding_box[5],
        )
        self.class_tag = class_tag

    def __str__(self) -> str:
        return f"DetectedObject(object_number: {self.object_number}, area: {self.area}, centroid: {self.centroid}, bounding_box: {self.bounding_box}, class_tag: {self.class_tag})"


class JsonLesion:
    id: int
    x: float
    y: float
    radius: float

    def __init__(self, id, x, y, radius):
        self.id = id
        self.x = x
        self.y = y
        self.radius = radius


class Lesion:
    id: int
    body_part: int
    area: float64
    centroid: tuple[float]
    bounding_box: tuple[int]

    def __init__(self, id, area, centroid, bounding_box, body_part):
        # 0 = torso
        # 1 = left leg
        # 2 = either arm
        # 3 = right leg
        self.id = id
        self.area = area
        self.centroid = centroid
        self.bounding_box = bounding_box
        self.body_part = body_part

    def get_radius(self):
        x_len = self.bounding_box[2] - self.bounding_box[0]
        y_len = self.bounding_box[3] - self.bounding_box[1]
        return (((x_len / 2) ** 2) + ((y_len / 2) ** 2)) ** 0.5

    def __str__(self) -> str:
        return f"Lesion(id: {self.id}, area: {self.area}, centroid: {self.centroid}, bounding_box: {self.bounding_box}, body_part: {self.body_part})"


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


def uploadLesionInfo(key: str, data: str):
    s3 = boto3.resource("s3")
    bucket = s3.Bucket("comp413")
    obj = bucket.Object(key)
    obj.put(Body=data.encode("utf-8"))
    obj.wait_until_exists()


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


def downloadLesionInfo(img: Image):
    s3 = boto3.client("s3")
    buf = io.BytesIO()
    s3.download_fileobj("comp413", img.imageUrl + ".lesions.json", buf)
    return buf.getvalue().decode("utf-8")


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

    lesionPred = get_lesion_predictor()
    segmentPred = get_segmentation_predictor()

    lesions = predictObjs(lesionPred, im)
    bodyParts = predictObjs(segmentPred, im)

    segmentedLesions = associateLesionToBodyPart(lesions, bodyParts)
    return segmentedLesions


def associateLesionToBodyPart(
    lesions: List[DetectedObject], bodyParts: List[DetectedObject]
) -> List[Lesion]:
    lesion_list = []
    for lesion in lesions:
        found = False
        for bodyPart in bodyParts:
            if isInside(lesion.centroid, lesion.bounding_box, bodyPart.bounding_box):
                # this lesion is inside this body part!
                lesion_list.append(
                    Lesion(
                        lesion.object_number,
                        lesion.area,
                        lesion.centroid,
                        lesion.bounding_box,
                        bodyPart.class_tag,
                    )
                )
                found = True
                break
        if not found:
            lesion_list.append(
                Lesion(
                    lesion.object_number,
                    lesion.area,
                    lesion.centroid,
                    lesion.bounding_box,
                    -1,
                )
            )
    return lesion_list


def isInside(center: tuple[float], bbox: tuple[int], container: tuple[int]):
    if not containsPoint(center, container):
        return False

    # TODO: 90% of the lesion is inside
    # check if the corner points are inside
    top_left = (bbox[0], bbox[1])
    top_right = (bbox[2], bbox[1])
    bottom_left = (bbox[0], bbox[3])
    bottom_right = (bbox[2], bbox[3])

    return (
        containsPoint(top_left, container)
        and containsPoint(top_right, container)
        and containsPoint(bottom_left, container)
        and containsPoint(bottom_right, container)
    )


def containsPoint(pt: tuple[float], box: tuple[int]):
    return pt[0] <= box[2] and pt[0] >= box[0] and pt[1] >= box[1] and pt[1] <= box[3]


def predictObjs(pred: DefaultPredictor, im):
    outputs = pred(im)

    # Convert the predicted mask to a binary mask
    mask = outputs["instances"].pred_masks.to("cpu").numpy().astype(bool)
    class_labels = outputs["instances"].pred_classes.to("cpu").numpy()

    # Use skimage.measure.regionprops to calculate object parameters
    labeled_mask = label(mask)
    props = regionprops(labeled_mask)

    # map each object
    return [propsToDetectedObj(prop, i, class_labels) for i, prop in enumerate(props)]


def propsToDetectedObj(prop, idx, labels):
    object_number = idx + 1  # Object number starts from 1
    area = prop.area
    centroid = prop.centroid
    bounding_box = prop.bbox

    # Check if the corresponding class label exists
    if idx < len(labels):
        class_name = labels[idx]
    else:
        # If class label is not available (should not happen), use 'Unknown' as class name
        class_name = -1

    return DetectedObject(object_number, area, centroid, bounding_box, class_name)


def get_lesion_predictor():
    cfg = get_cfg()
    cfg.merge_from_file("./models/detection_model/config.yaml")
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.2
    cfg.MODEL.WEIGHTS = "./models/detection_model/model.pth"
    if platform.system() == "Darwin":
        cfg.MODEL.DEVICE = "cpu"
    return DefaultPredictor(cfg)


def get_segmentation_predictor():
    cfg = get_cfg()
    cfg.merge_from_file("./models/segmentation_model/config.yaml")
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.2
    cfg.MODEL.WEIGHTS = "./models/segmentation_model/model.pth"
    if platform.system() == "Darwin":
        cfg.MODEL.DEVICE = "cpu"
    return DefaultPredictor(cfg)

def map_and_match(l1: List[JsonLesion], l2: List[JsonLesion]):
    len_a = len(l1)
    len_b = len(l2)
    distance_matrix = ot.dist(
        np.array([(l.x, l.y) for l in l1]),
        np.array([(l.x, l.y) for l in l2]),
        metric="euclidean",
    )
    row_ind, col_ind = scipy.optimize.linear_sum_assignment(distance_matrix)

    pairs = []

    for i in range(len(row_ind)):
        row = row_ind[i]
        col = col_ind[i]
        pairs.append({"a": l1[row].id, "b": l2[col].id, "distance": distance_matrix[row, col]})
    
    unmatched = set()
    a_set = set(row_ind)
    b_set = set(col_ind)

    if len_a >= len_b:
        for i in range(len_a):
            if i not in b_set:
                unmatched.add(i)
    else:
        for i in range(len_b):
            if i not in a_set:
                unmatched.add(i)
                
    # change this as necessary, mark pairs that we don't want to match bc distance is too great
    threshold = 20
    for pair in pairs:
        if pair["distance"] > threshold:
            unmatched.add(pair["a"])

    pairs = [pair for pair in pairs if pair["a"] not in unmatched]

    # return unmatched as well?

    return pairs
