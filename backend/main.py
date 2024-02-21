from flask import Flask, request
from db import init, getSession, User

app = Flask(__name__)

init()

with getSession() as session:
    user = User(name="John", role="doctor")


@app.route("/")
def hello_world():
    return "Hello!"


@app.route("/upload")
def upload():
    request.files["file"]
