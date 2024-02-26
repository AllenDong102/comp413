import json
from flask import Flask, redirect, request
from auth import SessionUser
from db import init, getSession, User
from dotenv import load_dotenv
from service import uploadImage, getUser, createUser, getUserGoogle
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

load_dotenv()

app = Flask(__name__)
app.secret_key = (
    b"\x10r=\xf7Z\xbe\xaf2\xc7\xeb\x0b\xab\xda\xb8\xc7\x1a\x96~\x9e\xae\x0bXlk"
)

init()

login_manager = LoginManager()
login_manager.init_app(app)
client = WebApplicationClient(os.getenv("GOOGLE_CLIENT_ID"))


config = None


def get_google_provider_cfg():
    global config
    if config == None:
        config = requests.get(os.getenv("GOOGLE_DISCOVERY_URL")).json()
    return config


@login_manager.user_loader
def load_user(user_id):
    # TODO: fix this
    return SessionUser(getUser(user_id), True, True, False)


@app.route("/")
def hello_world():
    return "Hello!"


@app.route("/upload")
def upload():
    file = request.files["file"]
    key = uploadImage(file)
    return "Uploaded! " + key


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

    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(os.getenv("GOOGLE_CLIENT_ID"), os.getenv("GOOGLE_CLIENT_SECRET")),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    res = userinfo_response.json()
    if res.get("email_verified"):
        g_id = res["sub"]
        existing = getUserGoogle(g_id)
        if existing != None:
            # user already exists!
            # todo: issue auth token
            login_user(existing)
        else:
            # create a user
            existing = createUser(res["given_name"], "doctor", res["sub"])

        login_user(SessionUser(existing, True, True, False))
        return redirect(os.getenv("FRONTEND_LOGIN_REDIRECT"))
    else:
        return "User email not available or not verified by Google.", 400
