import os
import firebase_admin
from firebase_admin import credentials


def initialize_firebase():
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    cred = credentials.Certificate(os.path.join(BASE_DIR, "firebase-admin.json"))

    firebase_app = firebase_admin.initialize_app(cred)

    return firebase_app


initialize_firebase()
