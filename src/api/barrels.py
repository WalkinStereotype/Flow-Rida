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
    redMlGained = 0
    greenMlGained = 0
    blueMlGained = 0
    darkMlGained = 0
    goldSpent = 0

    # Update mL and gold
    for b in barrels_delivered:

        if("RED" in b.sku):
            redMlGained += b.ml_per_barrel * b.quantity 
        elif("GREEN" in b.sku):
            greenMlGained += b.ml_per_barrel * b.quantity 
        elif("BLUE" in b.sku):
            blueMlGained += b.ml_per_barrel * b.quantity 
        elif("DARK" in b.sku):
            darkMlGained += b.ml_per_barrel * b.quantity 
        else:
            print("bro what\n")

        goldSpent = b.price * b.quantity


    with db.engine.begin() as connection:

        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml + {greenMlGained}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold - {goldSpent}"))

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    with db.engine.begin() as connection:
        numGreenPot = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar_one()
        goldInHand = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar_one()
    
    goldNeeded = 0

    for b in wholesale_catalog:
        if b.sku == "SMALL_GREEN_BARREL":
            goldNeeded = b.price
            break

    if(numGreenPot < 10 and goldInHand > goldNeeded and goldNeeded > 0):
        return [
            {
                "sku": "SMALL_GREEN_BARREL",
                "quantity": 1,
            }
        ]
    else:
        return[]
