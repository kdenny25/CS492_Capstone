import datetime
import uuid
from flask import session, flash
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

class User(UserMixin):

    def __init__(self, fName, lName, email, password, _id):

        self.fName = fName
        self.lName = lName
        self.email = email
        self.password = password
        self._id = _id

    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return self._id

    @classmethod
    def get_by_username(cls, username, db):
        data = db.find_one("users", {"username": username})
        if data is not None:
            return cls(**data)

    @classmethod
    def get_by_email(cls, email, db):
        data = db.find_one("users", {"email": email})
        if data is not None:
            return cls(**data)

    @classmethod
    def get_by_id(cls, _id, db):
        data = db.find_one("users", {"_id": _id})
        if data is not None:
            return cls(**data)


    def json(self):
        return {
            "first_name": self.fName,
            "last_name": self.lName,
            "email": self.email,
            "_id": self._id,
            "password": self.password
        }

    def save_to_mongo(self, db):
        db.insert("users", self.json())