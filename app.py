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
from werkzeug.utils import secure_filename
#from azure.storage.blob import BlobClient

base_dir = '.'

app = Flask(__name__,
            static_folder=os.path.join(base_dir, 'static'),
            template_folder=os.path.join(base_dir, 'templates'),)

# User session management setup
login_manager = LoginManager()
login_manager.init_app(app)

# Hashing method for user passwords
bcrypt = Bcrypt(app)

# csrf protection
csrf = CSRFProtect(app)

# todo: allow login with google credentials
# OAuth 2 client setup
# gClient = WebApplicationClient(GOOGLE_CLIENT_ID)

container_name = 'images'

# checks if local development environment or production environment and
# connects to correct MongoDB database.
if 'COSMOS_CONNECTION_STRING' not in os.environ:
    # local development, where environment variables are used
    print('Loading config.development and environment variables from .env file.')
    client = MongoClient('localhost', 27017)
    # file storage path
    # app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, "static/uploaded_images/")
    blob_conn_str = "DefaultEndpointsProtocol=https;AccountName=ctucapstonestg;AccountKey=/kF8zvrGJ8LsON1fd/TfTF79mrlmBYj/XiXN+o7USfDxbWtsWZPwYAa/Sz7sthSZL2BMowH0fqOR+ASt1TQqpA==;EndpointSuffix=core.windows.net"
    app.secret_key = b'_53oi3uriq9pifpff;apl'
    host_name="http://ctucapstone.azurewebsites.net/"
else:
    # production
    print('Loading config.production.')
    app.config.from_object('project_settings.production')
    conn_str = app.config.get('CONN_STRING')
    client = MongoClient(conn_str)
    host_name=request.base_url
    # image storage
    blob_conn_str = app.config.get('BLOB_CONN_STRING')


# sets up database
db = client.pizza_db

# database collections
orders = db.orders
getInTouch = db.getInTouch
users = db.users
menu_categories = db.menuCategories
menu_dishes = db.menuDishes
beverages = db.menuBeverages
toppings = db.menuToppings

# this is called when the user is loaded into a webpage
@login_manager.user_loader
def load_user(user_id):
    user = users.find_one({'_id': ObjectId(user_id)})
    if user is not None:
        return User(user)
    else:
        return None

@app.route('/')
def home_page():
    # opens homepage
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # gets data from form when POST method is passed
        email = request.form.get('email')
        password = request.form.get('password')

        # finds user in database and assigns profile details to find_user
        find_user = users.find_one({'email': email})

        # if user successfully found check if password is correct and log user in
        if find_user is not None:
            if bcrypt.check_password_hash(find_user['password'], password):
                # assign user details (in JSON format) to the User class
                log_user = User(find_user)
                login_user(log_user)

                # redirect to homepage
                return redirect('/')
            else:
                # passes an error message to login page.
                flash('Password is incorrect.', 'error')

        # passes error message to login page
        flash('User does not exist.', 'error')

        # if user does not exist returns user to login page with error message
        return render_template('elements/login_modal.html')

    # default GET response is to load the login page
    return render_template('elements/login_modal.html')

@app.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # gets data from the form
        fName = request.form.get('fName')
        lName = request.form.get('lName')
        email = request.form.get('email')

        # default assignment for role
        role = 'customer'

        # encrypt password before saving to database
        password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')

        # find if user email already exists
        find_user = users.find_one({'email': email})

        # if email doesn't already exist then create new user
        if find_user is None:
            _id = users.insert_one({'first_name': fName,
                                    'last_name': lName,
                                    'email': email,
                                    'role': role,
                                    'password': password})
            # sends message if registration is successful
            flash(f'Account created for {fName}!', 'success')
            # returns user to homepage with success message
            return redirect('/')
        else:
            # if user already exists sends error message
            flash(f'Account already exits for email: {email}!', 'error')

    # default response is to load registration page.
    return render_template('elements/register_modal.html')

@app.route('/logout')
@login_required
def logout():
    # log user out and redirect to home page
    logout_user()
    return redirect("/")

@app.route('/admin_dashboard')
@login_required
def admin_dash():
    # checks if user is admin before loading page.
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
        flash('Profile: ' + str(id) + ' successfully deleted.', 'success')
        return redirect('/user_management')
    return redirect('/')

@app.route('/menu_management', methods=['GET', 'POST'])
def admin_menu_management():
    if current_user.is_admin:
        if request.method == 'GET':
            count_cats = menu_categories.count_documents({})
            count_bevs = beverages.count_documents({})
            count_tops = toppings.count_documents({})
            count_dishes = menu_dishes.count_documents({})

            dish_categories = list(menu_categories.find({'category_type': 'dish'}))
            beverage_categories = list(menu_categories.find({'category_type': 'beverage'}))
            topping_categories = list(menu_categories.find({'category_type': 'topping'}))

            bev_options = list(beverages.find())
            dish_options = list(menu_dishes.find())

            bev_dict = {}

            for bev_cat in beverage_categories:
                bev_list = []
                for bev in bev_options:
                    if bev['category'] == bev_cat['category']:
                        bev_list.append(bev)
                bev_cat['bev_list'] = bev_list

            for dish_cat in dish_categories:
                dish_list = []
                for dish in dish_options:
                    if dish['category'] == dish_cat['category']:
                        dish_list.append(dish)
                dish_cat['dish_list'] = dish_list

            counts = {'menu_items': count_dishes,
                      'categories': count_cats,
                      'beverages': count_bevs,
                      'toppings': count_tops}

            page_data = {'counts': counts,
                         'dish_categories': dish_categories,
                         'bev_categories': beverage_categories,
                         'top_categories': topping_categories}


            return render_template('admin_dashboard/admin_menu_management.html', menu_data=page_data)
    return redirect('/')

@app.post('/add_menu_category')
def add_menu_category():
    if current_user.is_admin:
        category_type = request.form.get('categoryType')
        category = request.form.get('categoryName')

        find_category = menu_categories.find_one({'category_type': category_type,
                                                  'category': category})

        if find_category is None:
            menu_categories.insert_one({'category_type': category_type,
                                        'category': category})
            flash('Category ' + category + ' successfully added.', 'success')
            return redirect('/menu_management')
        else:
            flash('Category already exists', 'error')
            return redirect('/menu_management')
    else:
        return redirect('/')

@app.post('/add_menu_beverage')
def add_menu_beverage():
    if current_user.is_admin:
        bev_name = request.form.get('beverageName')
        bev_image = request.files.get('beverageImage', None)
        #test
        bev_image_path = ''
        if bev_image is not None:
            try:
                bev_image_filename = './' + secure_filename(bev_image.filename)
                bev_image_upload = BlobClient.from_connection_string(
                    conn_str=blob_conn_str,
                    container_name=container_name,
                    blob_name=bev_image_filename)

                with open(bev_image.file.read(), "rb") as data:
                    bev_image_upload(data)

                bev_image_path = f"{host_name}/{container_name}/{bev_image_filename}"
            except:
                pass

        # bev_image_filepath = os.path.join(app.config['UPLOAD_FOLDER'],
        #                                   secure_filename(bev_image.filename))
        # bev_image.save(bev_image_filepath)
        bev_category = request.form.get('beverageCat')
        bev_description = request.form.get('beverageDescription')
        bev_cost = float(request.form.get('beverageCost'))
        bev_price = float(request.form.get('beveragePrice'))
        bev_net_profit = bev_price - bev_cost

        find_beverage = beverages.find_one({'beverage_name': bev_name})

        if find_beverage is None:
            beverages.insert_one({'name': bev_name,
                                  'image': bev_image_path,
                                  'category': bev_category,
                                  'dscription': bev_description,
                                  'cost': bev_cost,
                                  'price': bev_price,
                                  'net_profit': bev_net_profit})
            flash('Beverage successfully added.', 'success')
            redirect('/menu_management')
        else:
            flash('Beverage name already exists')
            redirect('/menu_management')

        return redirect('/menu_management')
    else:
        return redirect('/')

@app.post('/add_menu_topping')
def add_menu_topping():
    if current_user.is_admin:
        top_name = request.form.get('toppingName')
        top_category = request.form.getlist('toppingCategory')

        find_topping = toppings.find_one({'name': top_name})

        if find_topping is None:
            _id= toppings.insert_one({'name': top_name,
                                'categories': top_category})

            for cat in top_category:
                menu_categories.update_one({'category': cat}, {'$push': {
                                                                'toppings': {
                                                                    'top_name': top_name
                                                                }}})
            flash('Topping successfully added.', 'success')
            return redirect('/menu_management')

        flash('Topping already exists.', 'error')
        return redirect('/menu_management')
    else:
        return redirect('/')

@app.post('/add_menu_dish')
def add_menu_dish():
    if current_user.is_admin:
        dish_name = request.form.get('dishName')
        dish_image = request.files.get('dishImage', None)
        print(dish_image)

        dish_image_path = ''
        if dish_image is not None:
            try:
                dish_image_filename = './' + secure_filename(dish_image.filename)
                dish_image_upload = BlobClient.from_connection_string(
                    conn_str=blob_conn_str,
                    container_name=container_name,
                    blob_name=dish_image_filename)

                with open(dish_image.file.read(), "rb") as data:
                    dish_image_upload(data)

                dish_image_path = f"{host_name}/{container_name}/{dish_image_filename}"
            except:
                pass


        #dish_image_filepath = os.path.join(app.config['UPLOAD_FOLDER'],
                                          #secure_filename(dish_image.filename))
        #dish_image.save(dish_image_filepath)
        dish_category = request.form.get('dishCat')
        dish_description = request.form.get('dishDescription')
        dish_cost = float(request.form.get('dishCost'))
        dish_price = float(request.form.get('dishPrice'))
        dish_net_profit = dish_price - dish_cost

        find_dish = menu_dishes.find_one({"name": dish_name})

        if find_dish is None:
            menu_dishes.insert_one({'name': dish_name,
                                    'image': dish_image_path,
                                    'category': dish_category,
                                    'description': dish_description,
                                    'cost': dish_cost,
                                    'price': dish_price,
                                    'net_profit': dish_net_profit})
            flash('Dish added successfully', 'success')
            return redirect('/menu_management')
        else:
            flash('Dish already exists', 'error')
            return redirect('/menu_management')
    else:
        return redirect('/')

# inserts communication responses from customers
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
