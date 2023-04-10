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

# this is called when the user is loaded into a webpage
@login_manager.user_loader
def load_user(user_id):
    user = users.find_one({'_id': ObjectId(user_id)})
    if user is not None:
        return User(user)
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

        #pulls all user details from users collection
        find_user = users.find_one({'email': email})
        if find_user is not None:
            if bcrypt.check_password_hash(find_user['password'], password):
                # assign user details (in JSON format) to the User class
                log_user = User(find_user)
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
        role = 'customer'
        password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')

        find_user = users.find_one({'email': email})

        if find_user is None:
            _id = users.insert_one({'first_name': fName,
                                    'last_name': lName,
                                    'email': email,
                                    'role': role,
                                    'password': password})
            # sends message if registration is successful
            flash(f'Account created for {fName}!', 'success')
            return redirect('/')
        else:
            flash(f'Account already exits for email: {email}!', 'error')
    return render_template('elements/register_modal.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")

@app.route('/admin_dashboard')
@login_required
def admin_dash():
    if current_user.is_admin:
        return render_template("admin_dashboard/admin_dashboard.html")
    else:
        return redirect('/')

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

    return render_template('admin_dashboard/communications.html', comm_results=comm_results)

@app.route('/user_management', methods=['GET', 'POST'])
def user_management():
    if current_user.is_admin:
        if request.method == 'POST':
            user_profiles = users.find()
            return render_template('admin_dashboard/user_management.html', user_profiles=user_profiles)

        return render_template('admin_dashboard/user_management.html', user_profiles=[])
    else:
        return redirect('/')

@app.route('/admin_user_profile')
def admin_user_profile():
    if current_user.is_admin:
        id = request.values.get("_id")

        edit_user = users.find_one({'_id': ObjectId(id)})
        return render_template('admin_dashboard/admin_user_profile.html', user_profile=edit_user)
    return redirect('/')

@app.post('/admin_update_user')
def admin_update_user():
    if current_user.is_admin:
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        role = request.form.get('role')

        id = request.values.get("_id")

        users.update_one({'_id': ObjectId(id)}, {'$set':{
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'role': role
        }})
        flash('Profile successfully updated.', 'success')
        return redirect('/admin_user_profile?_id=' + str(id))
    return redirect('/')

@app.route('/admin_delete_profile')
def admin_delete_profile():
    if current_user.is_admin:
        id = request.values.get("_id")
        users.delete_one({'_id': ObjectId(id)})
        flash('Profile: ' + str(id) + ' successfully deleted.')
        return redirect('/user_management')
    return redirect('/')


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
