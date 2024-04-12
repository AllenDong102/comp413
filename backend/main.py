import datetime
import json
import threading
from flask import Flask, Response, jsonify, redirect, request, session
from dotenv import load_dotenv
from auth import SessionUser
from api import GetUserResponse, PatientData
from db import init, getSession, User, Patient, Image
from service import (
    JsonLesion,
    createImage,
    downloadLesionInfo,
    getImageUrl,
    getLesions,
    map_and_match,
    uploadImage,
    getUser,
    createUser,
    getUserGoogle,
    getPatient,
    getImage,
    createPatient,
    uploadLesionInfo,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import os
import requests
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)

app.secret_key = (
    b"\x10r=\xf7Z\xbe\xaf2\xc7\xeb\x0b\xab\xda\xb8\xc7\x1a\x96~\x9e\xae\x0bXlk"
)
app.config["SESSION_COOKIE_DOMAIN"] = "localhost"

app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True

init()
login_manager = LoginManager()
login_manager.init_app(app)
client = WebApplicationClient(os.getenv("GOOGLE_CLIENT_ID"))


config = None


@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(minutes=20)


def get_google_provider_cfg():
    global config
    if config == None:
        config = requests.get(os.getenv("GOOGLE_DISCOVERY_URL")).json()
    return config


@login_manager.user_loader
def load_user(user_id):
    user = getUser(user_id)
    if user == None:
        return SessionUser(None, False, False, False)
    return SessionUser(getUser(user_id), True, True, False)


@app.route("/")
def hello_world():
    res = Response("hello!")
    return res


# {
#     "lesions": [
#         {
#             "x": 0,
#             "y": 0,
#             "radius": 0
#         }
#     ]
# }
@app.route("/lesion")
def run_model():
    id = int(request.args.get("id"))
    img = getImage(id)

    return Response(downloadLesionInfo(img), mimetype="application/json")


@app.route("/match")
def match2():
    idA = int(request.args.get("a"))
    idB = int(request.args.get("b"))
    imgA = getImage(idA)
    imgB = getImage(idB)

    infoA = downloadLesionInfo(imgA)
    infoB = downloadLesionInfo(imgB)
    arr1 = json.loads(infoA)["lesions"]
    arr2 = json.loads(infoB)["lesions"]

    l1 = [JsonLesion(x["id"], x["x"], x["y"], x["radius"]) for x in arr1]
    l2 = [JsonLesion(x["id"], x["x"], x["y"], x["radius"]) for x in arr2]
    res = map_and_match(l1, l2)
    asJson = {"mappings": res}

    return jsonify(asJson)


# {
#   "name": "name",
#   "id": "...",
#   "role": "doctor",
#   "patients": [
#     {
#       "name": "",
#       "id": ""
#     }
#   ]
# }
@app.route("/user")
def get_user():
    print(repr(session))
    print(current_user.get_id())
    if not current_user.is_authenticated:
        return "Not authenticated", 401

    return {
        "id": current_user.user.id,
        "name": current_user.user.name,
        "role": current_user.user.role,
        "patients": [{"name": p.name, "id": p.id} for p in current_user.user.patients],
    }


def is_doctor():
    return current_user.is_authenticated and current_user.user.role == "doctor"


@app.post("/upload")
def upload():
    # if not is_doctor():
    #     return "Not authenticated", 401
    id = int(request.args.get("id"))

    file = request.files["file"]
    key = uploadImage(file)
    img = createImage(key, id)

    # detect the lesions
    def process():
        processLesions(img)

    thread = threading.Thread(target=process)
    thread.start()

    return {"id": img.id, "url": getImageUrl(img.imageUrl)}


def processLesions(img: Image):
    lesions = getLesions(img.id)

    jsonData = {
        "lesions": [
            {
                "x": float(lesion.centroid[1]),
                "y": float(lesion.centroid[0]),
                "radius": float(lesion.get_radius()),
                "bodyPart": int(lesion.body_part),
                "id": lesion.id,
            }
            for lesion in lesions
        ]
    }

    uploadLesionInfo(img.imageUrl + ".lesions.json", json.dumps(jsonData))


@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    print("hello 4again")

    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    print("hello 2again")

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(os.getenv("GOOGLE_CLIENT_ID"), os.getenv("GOOGLE_CLIENT_SECRET")),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))
    print("hello again")

    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    print("hello")

    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    res = userinfo_response.json()
    if res.get("email_verified"):
        g_id = res["sub"]
        existing = getUserGoogle(g_id)
        if existing == None:
            # create a user
            print("creating a user! " + res["given_name"])
            existing = createUser(res["given_name"], "doctor", res["sub"])
        print("logging in " + existing.name)
        login_user(SessionUser(existing, True, True, False))
        return redirect(os.getenv("FRONTEND_LOGIN_REDIRECT"))
    else:
        return "User email not available or not verified by Google.", 400


@app.post("/patient")
def create_patient():
    if not is_doctor():
        return "Not authenticated", 401

    name = request.json["name"]

    created = createPatient(name, current_user.user.id)
    return {"id": created.id}


@app.get("/patient")
def patient_id():
    if not current_user.is_authenticated:
        return "Not authenticated", 401

    id = int(request.args.get("id"))
    patient: Patient = getPatient(id)

    if patient == None:
        return "Not found", 404

    if patient.owner_id != current_user.user.id:
        return "Not found", 404

    return {
        "name": patient.name,
        "id": patient.id,
        "images": [
            {
                "url": getImageUrl(image.imageUrl),
                "timestamp": image.timestamp,
                "id": image.id,
            }
            for image in patient.images
        ],
    }


@app.route("/lesions")
def get_lesion():
    if not current_user.is_authenticated:
        return "Not authenticated", 401

    # image id
    id = int(request.args.get("id"))
    image: Image = getImage(id)
    pass
