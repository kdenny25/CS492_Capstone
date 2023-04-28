import pymongo.errors
from flask import Flask, request, render_template, url_for, redirect, flash, session
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
from backend.site_logging import log_site_traffic
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient


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

# checks if local development environment or production environment and
# connects to correct MongoDB database.
if 'COSMOS_CONNECTION_STRING' not in os.environ:
    # local development, where environment variables are used
    #print('Loading config.development and environment variables from .env file.')
    client = MongoClient('localhost', 27017)
    # file storage path
    # app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, "static/uploaded_images/")
    blob_conn_str = "DefaultEndpointsProtocol=https;AccountName=ctucapstonestg;AccountKey=/kF8zvrGJ8LsON1fd/TfTF79mrlmBYj/XiXN+o7USfDxbWtsWZPwYAa/Sz7sthSZL2BMowH0fqOR+ASt1TQqpA==;EndpointSuffix=core.windows.net"
    app.secret_key = b'_53oi3uriq9pifpff;apl'
    blob_service_client = BlobServiceClient.from_connection_string(blob_conn_str)
else:
    # production
    print('Loading config.production.')
    app.config.from_object('project_settings.production')
    conn_str = app.config.get('CONN_STRING')
    client = MongoClient(conn_str)

    # image storage
    blob_conn_str = app.config.get('BLOB_CONN_STRING')
    blob_service_client = BlobServiceClient.from_connection_string(blob_conn_str)

host_name="https://ctucapstonestg.blob.core.windows.net"
container_name = 'images'

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
        #if user.phone is Null:

        return User(user)
    else:
        return None

@app.route('/')
def home_page():
    if request.method == 'POST':

        return redirect('index.html')
    else:
        log_site_traffic(db)
        return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # gets data from form when POST method is passed
        email = request.form.get('email')
        password = request.form.get('password')
        print(email)
        # finds user in database and assigns profile details to find_user
        find_user = users.find_one({'email': email})
        print(find_user)
        # if user successfully found check if password is correct and log user in
        if find_user is not None:
            if bcrypt.check_password_hash(find_user['password'], password):
                # assign user details (in JSON format) to the User class
                log_user = User(find_user)
                login_user(log_user)

                # redirect to homepage
                return redirect(request.referrer)
            else:
                # passes an error message to login page.
                flash('Password is incorrect.', 'error')
                return redirect(request.referrer)
        else:
            # passes error message to login page
            flash('User does not exist.', 'error')

            # if user does not exist returns user to login page with error message
            return redirect(request.referrer)

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
            log_site_traffic(db)
            # returns user to homepage with success message
            return redirect(request.referrer)
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

@app.route('/user_profile')
@login_required
def user_profile():
    if current_user.is_authenticated:
        try:
            user_phone = str(users.find_one({'_id': ObjectId(current_user._id)})['phone'])
        except:
            user_phone = ""
        print(user_phone)
        return render_template('user_pages/user_profile.html', user_phone=user_phone)
    else:
        return redirect('/')

@app.route('/user_orders')
@login_required
def user_orders():
    if current_user.is_authenticated:
        log_site_traffic(db)
        return render_template('user_pages/user_orders.html')
    else:
        return redirect('/')

@app.route('/user_addresses')
@login_required
def user_addresses():
    if current_user.is_authenticated:

        # attempt to pull user addresses. If this key doesn't exist then create an empty array
        try:
            user = users.find_one({'_id': ObjectId(current_user._id)})
            addresses = user['addresses']
        except:
            addresses = []

        return render_template('user_pages/user_addresses.html', user_addresses=addresses)
    else:
        return redirect('/')

@app.post('/add_user_address')
@login_required
def add_user_address():
    if current_user.is_authenticated:
        _id = request.form.get('_id')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip = request.form.get('zip')
        default = str(request.form.get('defaultAddress'))

        if default == 'None':
            default = 'False'

        user_addrs = users.find_one({'_id': ObjectId(_id)})

        try:
            # if ['addresses'] doesn't exist this will throw an error and move to except:
            user_addrs['addresses']

            # if it does exist then check if default is true and change value of current default address
            if default == 'True':
                for address in user_addrs['addresses']:
                    if (address['default'] == 'True'):
                        users.update_one({'_id': ObjectId, 'addresses._id': address['_id']}, {'$set': {
                            'default': 'False'
                        }})

            # then add a new address to the list
            users.update_one({'_id': ObjectId(_id)}, {'$push': {
                'addresses': {
                    '_id': ObjectId(),
                    'address': address,
                    'city': city,
                    'state': state,
                    'zip': zip,
                    'default': default
                }
            }})
        except:
            # if customer did not click default. Automatically set to default

            users.update_one({'_id': ObjectId(_id)}, {'$set': {
                 'addresses': [{
                     '_id': ObjectId(),
                     'address': address,
                     'city': city,
                     'state': state,
                     'zip': zip,
                     'default': 'True'
                 }]
             }})

        return redirect(request.referrer)
    else:
        return redirect('/')

@app.post('/update_user_name')
@login_required
def update_user_name():
    f_name = request.form.get('fName')
    l_name = request.form.get('lName')
    _id = request.form.get('_id')

    users.update_one({'_id': ObjectId(_id)}, {'$set': {
        'first_name': f_name,
        'last_name': l_name,
    }})

    flash('Name updated successfully', 'success')
    return redirect(request.referrer)

@app.post('/update_user_email')
@login_required
def update_user_email():
    email = request.form.get('email')
    _id = request.form.get('_id')

    users.update_one({'_id': ObjectId(_id)}, {'$set':{
        'email': email
    }})

    flash('Email updated successfully', 'success')
    return redirect(request.referrer)

@app.post('/update_user_phone')
@login_required
def update_user_phone():
    phone = request.form.get('phone')
    _id = request.form.get('_id')

    users.update_one({'_id': ObjectId(_id)}, {'$set':{
        'phone': phone
    }})

    flash('Phone number updated successfully', 'success')
    return redirect(request.referrer)

@app.post('/update_user_password')
@login_required
def update_user_password():
    new_password = request.form.get('newPass')
    old_password = request.form.get('oldPass')
    _id = request.form.get('_id')

    # find the current user in the database so we can pull the password
    find_user = users.find_one({'_id': ObjectId(_id)})

    # if the old password matches the stored password then we can change the password
    if bcrypt.check_password_hash(find_user['password'], old_password):
        password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        flash('Password updated successfully', 'success')
        return redirect(request.referrer)
    else:
        flash('Incorrect password used', 'error')
        return redirect(request.referrer)


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

@app.route('/dishes')           #This is strictly for the dishes.html page, not anyhting to with the db categories,etc.
def dishes():
    log_site_traffic(db)
    dish_categories = list(menu_categories.find({'category_type': 'dish'}))
    dish_options = list(menu_dishes.find())


    for dish_cat in dish_categories:
        dish_list = []
        dish_cat['_id'] = str(dish_cat['_id'])
        for dish in dish_options:
            dish['_id'] = str(dish['_id'])
            if dish['category'] == dish_cat['category']:
                dish_list.append(dish)
        dish_cat['dish_list'] = dish_list

    page_data = {'dish_categories': dish_categories}
    return render_template('dishes.html', menu_data=page_data)

@app.route('/wine')             #This is for the Winelist page, nothing to do with db otherwise.
def wine():
    log_site_traffic(db)
    return render_template('winelist.html')

@app.route('/story')            #For the Cacciatore's Story page (about the owners)
def story():
    return render_template('story.html')

@app.route('/elements')          #WE CAN TAKE THIS OUT IN THE FINAL PUSH, Leave it for now just in case but this is a developer's useful page only.
def elements():
    return render_template('elements.html')

@app.route('/menu')
def menu():
    dish_categories = list(menu_categories.find({'category_type': 'dish'}))
    beverage_categories = list(menu_categories.find({'category_type': 'beverage'}))
    dish_options = list(menu_dishes.find())
    bev_options = list(beverages.find())

    for bev_cat in beverage_categories:
        bev_list = []
        bev_cat['_id'] = str(bev_cat['_id'])
        for bev in bev_options:
            bev['_id'] = str(bev['_id'])
            if bev['category'] == bev_cat['category']:
                bev_list.append(bev)
        bev_cat['bev_list'] = bev_list

    for dish_cat in dish_categories:
        dish_list = []
        dish_cat['_id'] = str(dish_cat['_id'])
        for dish in dish_options:
            dish['_id'] = str(dish['_id'])
            if dish['category'] == dish_cat['category']:
                dish_list.append(dish)
        dish_cat['dish_list'] = dish_list

    page_data = {'dish_categories': dish_categories,
                 'bev_categories': beverage_categories}

    #log_site_traffic(db)

    return render_template('menu.html', menu_data=page_data)

@app.route('/order_review')
def order_review():
    # check if user is logged in
    if current_user.is_authenticated:
        user= users.find_one({'_id': ObjectId(current_user._id)})

        # try to pull the default address
        try:
            user_address = ''
            for address in user['addresses']:
                if address['default'] == 'True':
                    user_address = address

        except:
            user_address = ''

        return render_template('order_review.html', address=user_address)
    else:
        return render_template('order_review.html')

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
            all_categories = list(menu_categories.find())

            bev_options = list(beverages.find())
            dish_options = list(menu_dishes.find())

            for cat in all_categories:
                cat['_id'] = str(cat['_id'])

            for top in topping_categories:
                top['_id'] = str(top['_id'])

            for bev_cat in beverage_categories:
                bev_list = []
                bev_cat['_id'] = str(bev_cat['_id'])
                for bev in bev_options:
                    bev['_id'] = str(bev['_id'])
                    if bev['category'] == bev_cat['category']:
                        bev_list.append(bev)
                bev_cat['bev_list'] = bev_list

            for dish_cat in dish_categories:
                dish_list = []
                dish_cat['_id'] = str(dish_cat['_id'])
                for dish in dish_options:
                    dish['_id'] = str(dish['_id'])
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
                         'top_categories': topping_categories,
                         'all_categories': all_categories,
                         'all_dishes': dish_options}


            return render_template('admin_dashboard/admin_menu_management.html', menu_data=page_data)
    return redirect('/')

@app.post('/add_menu_dish')
def add_menu_dish():
    if current_user.is_admin:
        dish_name = request.form.get('dishName')
        dish_image = request.files.get('dishImage', None)

        dish_image_path = ''
        if dish_image.filename != '':
            filename = secure_filename(dish_image.filename)
            dish_image.save(filename)
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
            with open(filename, "rb") as data:
                try:
                    blob_client.upload_blob(data, overwrite=True)
                    print("Upload Done")

                    dish_image_path = f"{host_name}/{container_name}/{filename}"
                except:
                    pass
            os.remove(filename)

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
            return redirect(request.referrer)
        else:
            flash('Dish already exists', 'error')
            return redirect(request.referrer)
    else:
        return redirect('/')

@app.post('/update_menu_dish')
def update_menu_dish():
    if current_user.is_admin:
        dish_id = request.form.get('_id')
        dish_name = request.form.get('dishName')
        dish_image = request.files.get('dishImage', None)
        dish_category = request.form.get('dishCat')
        dish_description = request.form.get('dishDescription')
        dish_cost = float(request.form.get('dishCost'))
        dish_price = float(request.form.get('dishPrice'))
        dish_net_profit = dish_price - dish_cost

        print(dish_id)

        if dish_image.filename != '':
            filename = secure_filename(dish_image.filename)
            dish_image.save(filename)
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
            with open(filename, "rb") as data:
                try:
                    blob_client.upload_blob(data, overwrite=True)
                    print("Upload Done")
                    dish_image_path = f"{host_name}/{container_name}/{filename}"

                    # update database
                    menu_dishes.update_one({'_id': ObjectId(dish_id)}, {'$set':{
                        'name': dish_name,
                        'image': dish_image_path,
                        'category': dish_category,
                        'description': dish_description,
                        'cost': dish_cost,
                        'price': dish_price,
                        'net_profit': dish_net_profit
                    }})

                except:
                    pass
            os.remove(filename)

        else:
            # update database without image
            menu_dishes.update_one({'_id': ObjectId(dish_id)}, {'$set': {
                'name': dish_name,
                'category': dish_category,
                'description': dish_description,
                'cost': dish_cost,
                'price': dish_price,
                'net_profit': dish_net_profit
            }})

        flash('Dish updated successfully', 'success')
        return redirect(request.referrer)

    else:
        redirect('/')

@app.route('/delete_dish')
def delete_dish():
    if current_user.is_admin:
        _id = request.values.get('_id')

        dish_to_delete = menu_dishes.find_one({'_id': ObjectId(_id)})
        try:
            filename = dish_to_delete['image'][len(host_name+container_name)+2:]
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
            blob_client.delete_blob()
        except:
            pass

        menu_dishes.delete_one({'_id': ObjectId(_id)})

        return redirect(request.referrer)
    else:
        return redirect('/')

@app.route('/menu_management_categories', methods=['GET', 'POST'])
def admin_menu_management_categories():
    if current_user.is_admin:
        if request.method == 'GET':
            count_cats = menu_categories.count_documents({})
            count_bevs = beverages.count_documents({})
            count_tops = toppings.count_documents({})
            count_dishes = menu_dishes.count_documents({})

            dish_categories = list(menu_categories.find({'category_type': 'dish'}))
            beverage_categories = list(menu_categories.find({'category_type': 'beverage'}))
            topping_categories = list(menu_categories.find({'category_type': 'topping'}))
            all_categories = list(menu_categories.find())

            bev_options = list(beverages.find())
            dish_options = list(menu_dishes.find())

            for cat in all_categories:
                cat['_id'] = str(cat['_id'])

            for bev_cat in beverage_categories:
                bev_list = []
                for bev in bev_options:
                    bev['_id'] = str(bev['_id'])
                    if bev['category'] == bev_cat['category']:
                        bev_list.append(bev)
                bev_cat['bev_list'] = bev_list

            for dish_cat in dish_categories:
                dish_list = []
                for dish in dish_options:
                    dish['_id'] = str(dish['_id'])
                    if dish['category'] == dish_cat['category']:
                        dish_list.append(dish)
                dish_cat['dish_list'] = dish_list

            counts = {"menu_items": count_dishes,
                      "categories": count_cats,
                      "beverages": count_bevs,
                      "toppings": count_tops}

            page_data = {"counts": counts,
                         "dish_categories": dish_categories,
                         "bev_categories": beverage_categories,
                         "top_categories": topping_categories,
                         "all_categories": all_categories}

            return render_template('admin_dashboard/admin_elements/menu_management/admin_menu_management_categories.html', menu_data=page_data)
    return redirect('/')

@app.post('/update_menu_category')
def update_menu_category():
    if current_user.is_admin:
        _id = request.form.get('_id')
        cat_type = request.form.get('categoryType')
        category = request.form.get('categoryName')

        menu_categories.update_one({'_id': ObjectId(_id)}, {'$set':{
            'category_type': cat_type,
            'category': category
        }})
        flash('Category updated successfully', 'success')
        return redirect(request.referrer)

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
            return redirect(request.referrer)
    else:
        return redirect('/')

@app.route('/delete_category')
def delete_category():
    if current_user.is_admin:
        _id = request.values.get('_id')

        menu_categories.delete_one({'_id': ObjectId(_id)})

        return redirect(request.referrer)
    else:
        return redirect('/')

@app.route('/menu_management_beverages')
def view_beverage_menu():
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

            for bev_cat in beverage_categories:
                bev_list = []
                for bev in bev_options:
                    bev['_id'] = str(bev['_id'])
                    if bev['category'] == bev_cat['category']:
                        bev_list.append(bev)
                bev_cat['bev_list'] = bev_list

            for dish_cat in dish_categories:
                dish_list = []
                for dish in dish_options:
                    dish['_id'] = str(dish['_id'])
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

        return render_template('admin_dashboard/admin_elements/menu_management/admin_menu_management_beverages.html',
                               menu_data=page_data)
    return redirect('/')
@app.post('/add_menu_beverage')
def add_menu_beverage():
    if current_user.is_admin:
        bev_name = request.form.get('beverageName')
        bev_image = request.files.get('beverageImage', None)
        bev_image_path = ''

        if bev_image.filename != '':
            filename = secure_filename(bev_image.filename)
            bev_image.save(filename)
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
            with open(filename, "rb") as data:
                try:
                    blob_client.upload_blob(data, overwrite=True)
                    print("Upload Done")

                    bev_image_path = f"{host_name}/{container_name}/{filename}"
                except:
                    pass
            os.remove(filename)

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
                                  'description': bev_description,
                                  'cost': bev_cost,
                                  'price': bev_price,
                                  'net_profit': bev_net_profit})
            flash('Beverage successfully added.', 'success')
            return redirect(request.referrer)
        else:
            flash('Beverage name already exists')
            return redirect(request.referrer)

        return redirect(request.referrer)
    else:
        return redirect('/')

@app.post('/update_menu_beverage')
def update_menu_beverage():
    if current_user.is_admin:
        bev_id = request.form.get('_id')
        bev_name = request.form.get('bevName')
        bev_image = request.files.get('bevImage', None)
        bev_category = request.form.get('bevCat')
        bev_description = request.form.get('bevDescription')
        bev_cost = float(request.form.get('bevCost'))
        bev_price = float(request.form.get('bevPrice'))
        bev_net_profit = bev_price - bev_cost

        if bev_image.filename != '':
            filename = secure_filename(bev_image.filename)
            bev_image.save(filename)
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
            with open(filename, "rb") as data:
                try:
                    blob_client.upload_blob(data, overwrite=True)
                    print("Upload Done")
                    bev_image_path = f"{host_name}/{container_name}/{filename}"

                    # update database
                    beverages.update_one({'_id': ObjectId(bev_id)}, {'$set':{
                        'name': bev_name,
                        'image': bev_image_path,
                        'category': bev_category,
                        'description': bev_description,
                        'cost': bev_cost,
                        'price': bev_price,
                        'net_profit': bev_net_profit
                    }})

                except:
                    pass
            os.remove(filename)

        else:
            # update database without image
            beverages.update_one({'_id': ObjectId(bev_id)}, {'$set': {
                'name': bev_name,
                'category': bev_category,
                'description': bev_description,
                'cost': bev_cost,
                'price': bev_price,
                'net_profit': bev_net_profit
            }})

        flash('Beverage updated successfully', 'success')
        return redirect(request.referrer)

    else:
        redirect('/')
@app.route('/delete_beverage')
def delete_beverage():
    if current_user.is_admin:
        _id = request.values.get('_id')

        bev_to_delete = beverages.find_one({'_id': ObjectId(_id)})
        try:
            filename = bev_to_delete['image'][len(host_name+container_name)+2:]
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
            blob_client.delete_blob()
        except:
            pass

        beverages.delete_one({'_id': ObjectId(_id)})

        return redirect(request.referrer)
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
        return redirect(request.referrer)
    else:
        return redirect('/')

@app.route('/add_dish_to_cart', methods=['POST'])
def add_dish_to_cart():
    _id = request.form.get('_id')
    qty = int(request.form.get('qty'))
    tag = request.form.get('tag')   # determines if it is a beverage or dish

    # if the tag item is dish then we check the dish database else we check the beverage database
    if tag == 'dish':
        # pulls item information from dish database.
        item = menu_dishes.find_one({'_id': ObjectId(_id)})
        print(item)
    else:
        # pulls item information from beverages database
        item = beverages.find_one({'_id': ObjectId(_id)})
        print(item)

    # calculate total price of selected item once
    total_price = float(qty) * item['price']

    # create dict format of item to store in the session.
    item_dict = { '_id': str(item['_id']),
                 'name': item['name'],
                 'cost': item['cost'],
                 'price': item['price'],
                 'qty': qty,
                 'total_price': total_price}

    print("ID: " + str(_id) + " added " + str(qty) + " to cart")

    # if the key 'shopping_cart' is in the session then there are already items in the cart
    if 'shopping_cart' in session:
        print(session['shopping_cart'])
        # loop through cart and check if new item is already in shopping cart
        # if item is in cart then update qty
        # else append item to cart list and update total price and qty
        session['shopping_cart'].append(item_dict)
        session['total_quantity'] += qty
        session['total_price'] += total_price

    else:
        # initial setup of the cart, quantity and total price values
        session['shopping_cart'] = [item_dict]
        session['total_quantity'] = qty
        session['total_price'] = total_price
        print(session['shopping_cart'])

    return redirect(request.referrer)

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

# session info for cookies

