import random
from bson import ObjectId
from datetime import date

# randomly select cart items from the database

def gen_orders_data(db_dishes, db_bevs, date_start, date_end, min_daily_items, max_daily_items):
    zip_list = [80829, 80831, 80901, 80902, 80903, 80907, 80911, 80917, 80904, 80908, 80914, 80918]
    order_type_list = ['delivery', 'dine-in']

    house_id = ObjectId()

    delta_days = date(date_end) - date(date_start)

    item_dict = {'_id': str(item['_id']),
                 'name': item['name'],
                 'cost': item['cost'],
                 'price': item['price'],
                 'qty': qty,
                 'total_price': total_price}

    order = {'customer_id': house_id,
             'datetime': datetime.datetime.now(),
             'cart_items': cart_items,
             'total_price': total_price,
             'total_quantity': total_quantity,
             'delivery_address': {'address': None,
                                  'city': 'Colorado Springs',
                                  'state': 'CO',
                                  'zipcode': random.choice(zip_list)},
             'payment_type': payment_selection,
             'order_type': random.choice(order_type_list),
             'status': 'pending'}