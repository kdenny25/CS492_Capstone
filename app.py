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
from backend.orders_data_gen import gen_orders_data
from backend.user import User
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
bulletin = db.bulletinMessages

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

        user_orders = orders.find({'customer_id': current_user._id})
        return render_template('user_pages/user_orders.html', orders=user_orders)
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


@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
def admin_dash():
    # checks if user is admin before loading page.
    if current_user.is_admin:
        if request.method == 'GET':
            try:
                messages = bulletin.find()
            except:
                messages = []

            # checks if a manually entered start date exists.
            if request.values.get('start_date'):
                start_date = datetime.datetime.strptime(request.values.get('start_date') + 'T00:00:00', '%Y–%m-%dT%H:%M:%S')
                end_date = datetime.datetime.strptime(request.values.get('end_date') + 'T00:00:00', '%Y–%m-%dT%H:%M:%S')
                date_range = str(start_date) + ' - ' + str(end_date.date())


            else:
                start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0)
                date_range = str(start_date.date()) + ' - ' + str(start_date.date())

            visits_today = list(db.site_logs.find({'date': {'$gte': start_date}}))

            top_pages = {}
            for visit in visits_today:
                page = visit['referred_page'].replace(request.root_url, '/')
                if page not in top_pages:
                    top_pages[page] = 1
                else:
                    top_pages[page] +=1

            top_pages = dict(sorted(top_pages.items(), key=lambda item: item[1], reverse=True))

            data_to_display = {
                'pages_categories': list(top_pages.keys()),
                'pages_data': list(top_pages.values()),
                'date_range': date_range
            }

            print(data_to_display['pages_categories'])

            loc_data = []
            try:
                if len(visits_today) > 0:
                    for i in visits_today:
                        loc_data.append([float(i['ip_info']['latitude']),  float(i['ip_info']['longitude'])])
            except:
                pass

            return render_template("admin_dashboard/admin_dashboard.html", messages=messages, page_data=data_to_display, loc_data=loc_data)
    else:
        return redirect('/')

@app.post('/admin_add_bulletin')
@login_required
def admin_add_bulletin():
    # check if user is admin
    if current_user.is_admin:
        date = str(datetime.date.today().strftime("%m/%d/%Y"))
        user = current_user.fName + ' ' + current_user.lName
        message = request.form.get('msg')

        bulletin.insert_one({'date': date,
                             'user': user,
                             'message': message})

        return redirect(request.referrer)
    else:
        return redirect('/')

@app.route('/dishes')           #This is strictly for the dishes.html page, not anyhting to with the db categories,etc.
def dishes():
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

@app.route('/winelist')             #This is for the Winelist page, nothing to do with db otherwise.
def winelist():
    return render_template('winelist.html')

@app.route('/story')            #For the Cacciatore's Story page (about the owners)
def story():
    return render_template('story.html')

@app.route('/groupone')
def groupone():
    return render_template('groupone.html')

@app.route('/menu', methods=['GET', 'POST'])
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


    return render_template('menu.html', menu_data=page_data)

@app.route('/order_review')
def order_review():
    # check if user is logged in
    date = datetime.date.today()
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

        return render_template('order_review.html', address=user_address, date=date)
    else:
        return render_template('order_review.html', date=date)

@app.post('/order_confirmation')
def order_confirmation():
    if current_user.is_authenticated:
        # process order as a logged in customer
        try:
            # check if shopping cart has items.
            cart_items = session['shopping_cart']
            total_price = session['total_price']
            total_quantity = session['total_quantity']

            # delivery address
            address = request.form.get('address')
            city = request.form.get('city')
            state = request.form.get('state')
            zipcode = request.form.get('zip')

            payment_selection = request.form.get('paymentMethod')

            order = {'customer_id': current_user._id,
                     'datetime': datetime.datetime.now(),
                     'cart_items': cart_items,
                     'total_price': total_price,
                     'total_quantity': total_quantity,
                     'delivery_address': {'address': address,
                                          'city': city,
                                          'state': state,
                                          'zipcode': zipcode},
                     'payment_type': payment_selection,
                     'order_type': 'delivery',
                     'status': 'pending'}

            orders.insert_one(order)

            session.pop('shopping_cart', None)
            session.pop('total_price', None)
            session.pop('total_quantity', None)


            return render_template('order_confirmation.html', order=order)
        except:
            flash('No items in cart', 'error')
            return redirect(request.referrer)
    else:
        # process order as a guest
        try:
            # check if shopping cart has items.
            cart_items = session['shopping_cart']
            total_price = session['total_price']
            total_quantity = session['total_quantity']

            # guest delivery address
            address = request.form.get('gAddress')
            city = request.form.get('gCity')
            state = request.form.get('gState')
            zipcode = request.form.get('gZip')

            payment_selection = request.form.get('paymentMethod')

            order = {'customer_id': 'guest',
                     'datetime': datetime.datetime.now(),
                     'cart_items': cart_items,
                     'total_price': total_price,
                     'total_quantity': total_quantity,
                     'delivery_address': {'address': address,
                                          'city': city,
                                          'state': state,
                                          'zipcode': zipcode},
                     'payment_type': payment_selection,
                     'order_type': 'delivery',
                     'status': 'pending'}

            orders.insert_one(order)

            session.pop('shopping_cart', None)
            session.pop('total_price', None)
            session.pop('total_quantity', None)

            return render_template('order_confirmation.html', order=order)
        except:
            flash('No items in cart', 'error')
            return redirect(request.referrer)

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

@app.route('/admin_orders_dashboard')
def admin_orders_dashboard():
    if current_user.is_admin:
        order_list = list(orders.find())

        sales_total = 0
        expense_total = 0
        profit_total = 0

        daily_orders = {}

        for order in order_list:
            order_date = order['datetime'].date()
            for item in order['cart_items']:
                item_sale_total = item['total_price']
                item_expense_total = (item['cost'] * item['qty'])
                item_profit_total = item_sale_total - item_expense_total

                # add to timeframe total
                sales_total += item_sale_total
                expense_total += item_expense_total

                # add to daily total
                if order_date not in daily_orders:
                    daily_orders[order_date] = {'sales_total': item_sale_total,
                                                'expenses_total': item_expense_total,
                                                'item_profits_total': item_profit_total}
                else:
                    daily_orders[order_date]['sales_total'] += item_sale_total
                    daily_orders[order_date]['expenses_total'] += item_expense_total
                    daily_orders[order_date]['item_profits_total'] += item_profit_total

        daily_orders = dict(sorted(daily_orders.items(), key=lambda item: item[0], reverse=False))

        labels = [date.strftime('%Y-%m-%d') for date in list(daily_orders.keys())]

        sales_data = []
        expense_data = []
        profits_data = []

        for day in daily_orders:
            sales_data.append(daily_orders[day]['sales_total'])
            expense_data.append(daily_orders[day]['expenses_total'])
            profits_data.append(daily_orders[day]['item_profits_total'])

        # data_to_display = {
        #     'pages_categories': list(top_pages.keys()),
        #     'pages_data': list(top_pages.values())
        # }

        profit_total = sales_total - expense_total

        page_data = {
            "spark_labels": labels,
            "sales_total":  int(sales_total),
            "sales_data": sales_data,
            "expense_total": int(expense_total),
            "expense_data": expense_data,
            "profits_total": int(profit_total),
            "profits_data": profits_data
        }

        return render_template('admin_dashboard/admin_orders_dashboard.html', page_data=page_data)
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
    else:
        # pulls item information from beverages database
        item = beverages.find_one({'_id': ObjectId(_id)})

    # calculate total price of selected item once
    total_price = float(qty) * item['price']

    # create dict format of item to store in the session.
    item_dict = { '_id': str(item['_id']),
                 'name': item['name'],
                 'cost': item['cost'],
                 'price': item['price'],
                 'qty': qty,
                 'total_price': total_price}

    # if the key 'shopping_cart' is in the session then there are already items in the cart
    if 'shopping_cart' in session:
        # Get a temporary reference to the session cart, just to reduce the name of the variable we will use subsequently
        shopping_cart = session["shopping_cart"]
        # This flag will be used to track if the item exists or not
        itemExists = False
        for item in shopping_cart:
            # This flag will be used to track if the item exists or not

            if item["_id"] == _id:
                item["qty"] = item["qty"] + qty
                session['total_quantity'] += qty
                item['total_price']= item['total_price'] + total_price
                session['total_price'] += total_price
                itemExists = True
                break  # exit the for loop

        # Save the temp cart back into session
        session["shopping_cart"] = shopping_cart

        if not itemExists:
            session['shopping_cart'].append(item_dict)
            session['total_quantity'] += qty
            session['total_price'] += total_price

    else:
        # initial setup of the cart, quantity and total price values
        session['shopping_cart'] = [item_dict]
        session['total_quantity'] = qty
        session['total_price'] = total_price

    return json.dumps({'status': 'Success'})

@app.route('/delete_item')
def deleteitem():
   _id = request.values.get('_id')
   shopping_cart = session['shopping_cart']
   for index, value in enumerate(session['shopping_cart']):
        # remove the item from the session if it is there
        if  value['_id'] == _id:
            session['total_price'] = session['total_price'] - value['total_price']
            session['total_quantity'] = session['total_quantity'] - value['qty']
            shopping_cart.pop(index)
            if len(session['shopping_cart'])==0:
                session.pop('shopping_cart', None)
   session["shopping_cart"] = shopping_cart

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

@app.route('/log_visit')
def log_visit():
    try:
        site_logs = db.site_logs
        date = datetime.datetime.now()

        ip_result = {
            'ip': request.values.get('ip'),
            'network': request.values.get('network'),
            'version': request.values.get('version'),
            'city': request.values.get('city'),
            'region': request.values.get('region'),
            'region_code': request.values.get('region_code'),
            'country': request.values.get('country'),
            'country_name': request.values.get('country_name'),
            'country_code': request.values.get('country_code'),
            'country_code_iso3': request.values.get('country_code_iso3'),
            'country_capital': request.values.get('country_capital'),
            'country_tld': request.values.get('country_tld'),
            'continent_code': request.values.get('continent_code'),
            'in_eu': request.values.get('in_eu'),
            'postal': request.values.get('postal'),
            'latitude': request.values.get('latitude'),
            'longitude': request.values.get('longitude'),
            'timezone': request.values.get('timezone'),
            'utc_offset': request.values.get('utc_offset'),
            'country_calling_code': request.values.get('country_calling_code'),
            'languages': request.values.get('languages'),
            'country_area': request.values.get('country_area'),
            'country_population': request.values.get('country_population'),
            'asn': request.values.get('asn'),
            'org': request.values.get('org')
        }

        log = {'date': date,
               'ip_info': ip_result,
               'referred_page': str(request.referrer),
               'landing page': str(request.referrer)}

        site_logs.insert_one(log)

        return json.dumps({'status': 'Success'})
    except:
        print('error retrieving IP')
        pass

    return json.dumps({'status': 'Success'})

@app.route('/data_generator')
def data_generator():
    if current_user.is_admin:

        if request.values.get('start_date'):
            start_date = request.values.get('start_date')
            end_date = request.values.get('end_date')

            min_daily_order = int(request.values.get('min_orders'))
            max_daily_order = int(request.values.get('max_orders'))

            orders_generated = gen_orders_data(menu_dishes, beverages, orders, start_date, end_date, min_daily_order, max_daily_order)
            flash(orders_generated[0], orders_generated[1])
        return render_template('admin_dashboard/admin_data_generator.html')
    else:
        return redirect('/')

@app.route('/store_settings')
def store_settings():
    if current_user.is_admin:
        return render_template('admin_dashboard/admin_store_settings.html')
    else:
        return redirect('/')