from flask import request
import requests
import json
import datetime

def log_site_traffic(db):

    try:
        site_logs = db.site_logs
        date = datetime.datetime.now()
        ip_address = str(request.remote_addr)

        request_url = 'https://geolocation-db.com/jsonp/' + ip_address
        ip_response = requests.get(request_url)
        ip_result = ip_response.content.decode()
        ip_result = ip_result.split("(")[1].strip(")")
        print(ip_result)
        ip_result = json.loads(ip_result)

        log = {'date': date,
               'ip_info': ip_result,
               'referred_page': str(request.referrer),
               'landing page': str(request.path)}

        site_logs.insert_one(log)
    except:
        pass