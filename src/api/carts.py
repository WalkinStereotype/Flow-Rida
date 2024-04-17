import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum

# id = 0
# cartss = {}

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
    }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int

@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    print(customers)

    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    # global id
    # id += 1
    # INSERT INTO carts (customer_name) VALUES(customer_name) returning id

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(f"INSERT INTO carts (customer_name) VALUES ('{new_cart.customer_name}')"))
        return connection.execute(sqlalchemy.text(f"SELECT id FROM carts WHERE customer_name = '{new_cart.customer_name}' ORDER BY id desc LIMIT 1")).scalar_one()

    # return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int

# class Cart(BaseModel):
#     sku: str
#     potion_id: int
#     quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    # global cartss

    with db.engine.begin() as connection:
        potionId = connection.execute(sqlalchemy.text(f"SELECT id FROM potion_inventory WHERE sku = '{item_sku}'")).scalar_one()
        connection.execute(sqlalchemy.text(f"INSERT INTO cart_items (cart_id, potion_id, quantity) VALUES ({cart_id}, {potionId}, {cart_item.quantity})"))
    
    # if(cart_id not in cartss.keys()):
    #     cartss[cart_id] = []# {potionId : {}}
    # cartss[cart_id] += {
    #         "sku": item_sku,
    #         "potion_id": potionId,
    #         "quantity": cart_item.quantity
    #     } 
    

    
    #table called carts_items with composite key: (cart_id, potion_id) 
    

    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    totalBought = 0
    totalGoldPaid = 0
    
    with db.engine.begin() as connection:
        results = connection.execute(sqlalchemy.text(f"SELECT potion_id, quantity FROM cart_items WHERE cart_id = {cart_id}"))

        for cart_items in results:
            connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET quantity = quantity - {cart_items.quantity} WHERE id = {cart_items.potion_id}"))

            totalBought += cart_items.quantity
            totalGoldPaid += (cart_items.quantity * connection.execute(sqlalchemy.text(f"SELECT price from potion_inventory WHERE id = {cart_items.potion_id}")).scalar_one()) 

        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold + {totalGoldPaid}"))

        # for item in cartss[cart_id]:
        #     print(item)
        #     totalBought += item["quantity"]
        #     totalGoldPaid += (item["quantity"] * connection.execute(sqlalchemy.text(f"SELECT price FROM potion_inventory WHERE id = {item["potion_id"]}")).scalar_one())

        #     connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET quantity = quantity - {item["quantity"]} WHERE id = {item["potion_id"]}")).scalar_one()
        
        # connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold + {totalGoldPaid}"))

    return {"total_potions_bought": totalBought, "total_gold_paid": totalGoldPaid}
