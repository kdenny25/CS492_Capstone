import pymongo.errors
from flask import Flask, request, render_template, url_for, redirect, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient, ASCENDING
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, current_user,login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient
from bson.objectid import ObjectId
import numpy as np
import os, sys
import json
import datetime
from backend.user import User

base_dir = '.'

app = Flask(__name__,
            static_folder=os.path.join(base_dir, 'static'),
            template_folder=os.path.join(base_dir, 'templates'),)

# User session management setup
login_manager = LoginManager()
login_manager.init_app(app)

# Hashing method for user passwords
bcrypt = Bcrypt(app)

csrf = CSRFProtect(app)

# todo: allow login with google credentials
# OAuth 2 client setup
# gClient = WebApplicationClient(GOOGLE_CLIENT_ID)

if 'COSMOS_CONNECTION_STRING' not in os.environ:
    # local development, where environment variables are used
    print('Loading config.development and environment variables from .env file.')
    client = MongoClient('localhost', 27017)
    app.secret_key = b'_53oi3uriq9pifpff;apl'
else:
    # production
    print('Loading config.production.')
    app.config.from_object('project_settings.production')
    conn_str = app.config.get('CONN_STRING')
    client = MongoClient(conn_str)

db = client.pizza_db

orders = db.orders
getInTouch = db.getInTouch
users = db.users

@login_manager.user_loader
def load_user(user_id):
    user = users.find_one({'_id': ObjectId(user_id)})
    if user is not None:
        return User(user["first_name"], user["last_name"], user["email"], user["password"], str(user["_id"]))
        print('User returned')
    else:
        return None

@app.route('/', methods=['GET', 'POST'])
def home_page():
    if request.method == 'POST':
        return redirect('index.html')
    else:
        print(current_user)
        return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        find_user = users.find_one({'email': email})
        if find_user is not None:
            if bcrypt.check_password_hash(find_user['password'], password):
                log_user = User(find_user['first_name'], find_user['last_name'], find_user['email'], find_user['password'], str(find_user['_id']))
                print(log_user.json())
                login_user(log_user)
                return redirect('/')
            else:
                flash('Password is incorrect.', 'error')

        flash('User does not exist.', 'error')
        return render_template('elements/login_modal.html')

    return render_template('elements/login_modal.html')

@app.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fName = request.form.get('fName')
        lName = request.form.get('lName')
        email = request.form.get('email')
        password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')

        find_user = users.find_one({'email': email})

        if find_user is None:
            _id = users.insert_one({'first_name': fName,
                                    'last_name': lName,
                                    'email': email,
                                    'password': password})
            flash(f'Account created for {fName}!', 'success')
        else:
            flash(f'Account already exits for email: {email}!', 'error')
    return render_template('elements/register_modal.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")

@app.route('/generic')
def generic():
    return render_template('generic.html')

@app.route('/elements')
def elements():
    return render_template('elements.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/communications')
def communications():
    comm_results = getInTouch.find()

    return render_template('communications.html', comm_results=comm_results)

@app.post('/get_in_touch')
def get_in_touch():
    name = request.form.get('name')
    date = datetime.datetime.now()
    email = request.form.get('email')
    message = request.form.get('message')
    viewed = 0

    getInTouch.insert_one({'date': date,
                             'name': name,
                             'email': email,
                             'message': message,
                             'viewed': viewed
                             })

    # ideally this would be a thank you for your comment page
    return redirect('/')
