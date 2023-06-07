import random
from bson import ObjectId
from datetime import date, datetime, timedelta
from pymongo import MongoClient

# randomly select cart items from the database
def gen_orders_data(db_dishes, db_bevs, db_orders, date_start = "2023–06-06", date_end= "2023–06-06", min_daily_orders = 1, max_daily_orders = 4):
    zip_list = [80829, 80831, 80901, 80902, 80903, 80907, 80911, 80917, 80904, 80908, 80914, 80918]
    order_type_list = ['delivery', 'dine-in']
    payment_type_list = ['cash', 'card']
    status_list = ['pending', 'complete']
    customer_id_list = [str(ObjectId), 'guest']
    print(date_start)
    date_start = datetime.strptime(date_start + 'T00:00:00', '%Y–%m-%dT%H:%M:%S')
    date_end = datetime.strptime(date_end + 'T00:00:00', '%Y-%m-%dT%H:%M:%S')
    delta_days = (date_end - date_start).days

    dishes_list = list(db_dishes.find())
    bevs_list = list(db_bevs.find())

    total_records = 0

    #try:
    # for each day
    for i in range(0, delta_days):
        # determine number of orders to generate
        num_orders = random.randint(min_daily_orders, max_daily_orders)
        orders_date = date_start + timedelta(days=i)

        # for each order
        for k in range(min_daily_orders, num_orders):
            total_price = 0
            total_qty = 0
            total_records += 1
            # items in each order
            num_items = random.randint(1, 6)
            cart_items = []
            for j in range(1, num_items):
                bev_or_dish = random.randint(0,1)

                # if bev_or_dish is 0 then select a dish
                if bev_or_dish == 0:
                    dish_item = random.randint(0, len(dishes_list)-1)
                    item_to_add = dishes_list[dish_item]

                else:   # else select a beverage
                    bev_item = random.randint(0, len(bevs_list)-1)
                    item_to_add = bevs_list[bev_item]

                # determine the quantity and total price
                qty = random.randint(1,5)
                item_total_price = item_to_add['price'] * qty

                # add qty and total price to order total qty and price
                total_qty += qty
                total_price += item_total_price

                item_dict = {'_id': str(item_to_add['_id']),
                             'name': item_to_add['name'],
                             'cost': item_to_add['cost'],
                             'price': item_to_add['price'],
                             'qty': qty,
                             'total_price': item_total_price}

                #append to cart_items
                cart_items.append(item_dict)

            orders_date = orders_date.replace(hour=random.randint(1,12), minute=random.randint(0,60))
            order_type = random.choice(order_type_list)

            if order_type == 'delivery':
                address ={'address': None,
                          'city': 'Colorado Springs',
                          'state': 'CO',
                          'zipcode': random.choice(zip_list)}
            else:
                address = None

            order = {'customer_id': random.choice(customer_id_list),
                     'datetime': orders_date,
                     'cart_items': cart_items,
                     'total_price': total_price,
                     'total_quantity': total_qty,
                     'delivery_address': address,
                     'payment_type': random.choice(payment_type_list),
                     'order_type': order_type,
                     'status': random.choice(status_list
                     )}
            print(order)
            db_orders.insert_one(order)

    return str(total_records) + "   record(s) created successfully", "success"
    # except:
    #     return 'There was an error completing this request', 'error'
