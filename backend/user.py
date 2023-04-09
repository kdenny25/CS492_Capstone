import datetime
import uuid
from flask import session, flash
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

class User(UserMixin):

    def __init__(self, json):
        # when pulled from the database the users credentials are
        # in json format. User() requires a json input to process all
        # user information. This is cleaner than including all values
        # in a sequence.
        self.fName = json['first_name']
        self.lName = json['last_name']
        self.email = json['email']
        self.role = json['role']
        self.password = json['password']
        self._id = str(json['_id'])

    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return self._id

    # returns true if user is admin.
    def is_admin(self):
        if self.role == 'admin':
            return True
        else:
            return False

    def json(self):
        return {
            "first_name": self.fName,
            "last_name": self.lName,
            "email": self.email,
            "role": self.role,
            "_id": self._id,
            "password": self.password
        }