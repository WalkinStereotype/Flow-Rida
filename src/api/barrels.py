import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    # Zero everything first
    mlGained = [0, 0, 0, 0]
    goldSpent = 0

    # Update mL and gold
    for b in barrels_delivered:

        if("RED" in b.sku):
            mlGained[0] += b.ml_per_barrel * b.quantity 
        elif("GREEN" in b.sku):
            mlGained[1] += b.ml_per_barrel * b.quantity 
        elif("BLUE" in b.sku):
            mlGained[2] += b.ml_per_barrel * b.quantity 
        elif("DARK" in b.sku):
            mlGained[3] += b.ml_per_barrel * b.quantity 
        else:
            print("bro what\n")

        goldSpent = b.price * b.quantity


    with db.engine.begin() as connection:

        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml + {mlGained[1]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_red_ml = num_red_ml + {mlGained[0]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_blue_ml = num_blue_ml + {mlGained[2]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_dark_ml = num_dark_ml + {mlGained[3]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold - {goldSpent}"))

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)
    pricesOfSmall = [-1, -1, -1]
    for barrel in wholesale_catalog:
        if barrel.sku == "SMALL_RED_BARREL":
            pricesOfSmall[0] = barrel.price
        elif barrel.sku == "SMALL_GREEN_BARREL":
            pricesOfSmall[1] = barrel.price
        elif barrel.sku == "SMALL_BLUE_BARREL":
            pricesOfSmall[2] = barrel.price


    with db.engine.begin() as connection:
        numGreenPot = connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 1")).scalar_one()
        numRedPot = connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 2")).scalar_one()
        numBluePot = connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 3")).scalar_one()
        goldInHand = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar_one()

    
    goldNeeded = 0
    plan = []

    if(numGreenPot <= numRedPot and numGreenPot <= numBluePot and goldInHand >= goldNeeded + pricesOfSmall[1]):
        plan.append(
            {
                "sku": "SMALL_GREEN_BARREL",
                "quantity": 1
            }
        )
        goldNeeded += pricesOfSmall[1]
    if(numRedPot <= numGreenPot and numRedPot <= numBluePot and goldInHand >= goldNeeded + pricesOfSmall[0]):
        plan.append(
            {
                "sku": "SMALL_RED_BARREL",
                "quantity": 1
            }
        )
        goldNeeded += pricesOfSmall[0]
    if(numBluePot <= numGreenPot and numBluePot <= numRedPot and goldInHand >= goldNeeded + pricesOfSmall[2]): 
        plan.append(
            {
                "sku": "SMALL_BLUE_BARREL",
                "quantity": 1
            }
        )
        goldNeeded += pricesOfSmall[2]
    return plan

