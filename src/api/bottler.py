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

    with db.engine.begin() as connection:
        greenPotGained = potions_delivered[0].quantity
        mlUsed = 100 * greenPotGained

        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml -= {mlUsed}"))
        
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_potions += {greenPotGained}"))

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
        numGreenMl = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar_one()
        if(numGreenMl >= 100):
            numPotToMake = numGreenMl / 100
            return [
                    {
                        "potion_type": [0, 100, 0, 0],
                        "quantity": numPotToMake,
                    }
                ]

if __name__ == "__main__":
    print(get_bottle_plan())