import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    # Zero everything first
    mlUsed = [0, 0, 0, 0]
    potions = [0, 0, 0]

    for pot in potions_delivered:
        mlUsed[0] += pot.potion_type[0] * pot.quantity
        mlUsed[1] += pot.potion_type[1] * pot.quantity
        mlUsed[2] += pot.potion_type[2] * pot.quantity
        mlUsed[3] += pot.potion_type[3] * pot.quantity

        if pot.potion_type[0] == 100:
            potions[0] += pot.quantity
        elif pot.potion_type[1] == 100:
            potions[1] += pot.quantity
        elif pot.potion_type[2] == 100:
            potions[2] += pot.quantity
    


    with db.engine.begin() as connection:
        greenPotGained = potions_delivered[0].quantity

        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_red_ml = num_red_ml - {mlUsed[0]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml - {mlUsed[1]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_blue_ml = num_blue_ml - {mlUsed[2]}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_dark_ml = num_dark_ml - {mlUsed[3]}"))

        connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET quantity = quantity + {potions[0]} WHERE id = 2"))
        connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET quantity = quantity + {potions[1]} WHERE id = 1"))
        connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET quantity = quantity + {potions[2]} WHERE id = 3"))
        # connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET quantity = quantity + {potions[0] + potions[1] + potions[2]} WHERE id = 'total'"))

    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into red potions.
    with db.engine.begin() as connection:
        numMl = [0, 0, 0, 0]
        numPot = {}
        numMl[0] = connection.execute(sqlalchemy.text("SELECT num_red_ml FROM global_inventory")).scalar_one()
        numMl[1] = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar_one()
        numMl[2] = connection.execute(sqlalchemy.text("SELECT num_blue_ml FROM global_inventory")).scalar_one()
        list = []

        totalCurrPot = (connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 1")).scalar_one() +
                connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 2")).scalar_one() +
                connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 3")).scalar_one()
        )

        if(numMl[0] >= 100 and totalCurrPot < 50):
            numPotToMake = min( int(numMl[0] / 100) , 50 - totalCurrPot)
            list.append( 
                    {
                        "potion_type": [100, 0, 0, 0],
                        "quantity": numPotToMake,
                    }
            )
        if(numMl[1] >= 100):
            numPotToMake = min( int(numMl[1] / 100) , 50 - totalCurrPot)
            list.append(
                    {
                        "potion_type": [0, 100, 0, 0],
                        "quantity": numPotToMake,
                    }
            )
        if(numMl[2] >= 100):
            numPotToMake = min( int(numMl[2] / 100) , 50 - totalCurrPot) 
            list.append(
                    {
                        "potion_type": [0, 0, 100, 0],
                        "quantity": numPotToMake,
                    }
            )
        
        
        return list

if __name__ == "__main__":
    print(get_bottle_plan())