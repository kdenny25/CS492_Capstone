import pymongo.errors
from flask import Flask, request, render_template, url_for, redirect
from pymongo import MongoClient, ASCENDING
from flask_wtf.csrf import CSRFProtect
from bson.objectid import ObjectId
import numpy as np
import os, sys
import json
import datetime

base_dir = '.'

app = Flask(__name__,
            static_folder=os.path.join(base_dir, 'static'),
            template_folder=os.path.join(base_dir, 'templates'),)

csrf = CSRFProtect(app)

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


@app.route('/', methods=['GET', 'POST'])
def home_page():
    if request.method == 'POST':
        return redirect('indext.html')
    else:
        return render_template('index.html')

@app.route('/generic')
def generic():
    return render_template('generic.html')

@app.route('/elements')
def elements():
    return render_template('elements.html')

@app.route('/groupone')
def groupone():
    return render_template('groupone.html')

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
    return render_template('index.html')
