import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth

from sqlalchemy.exc import IntegrityError

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

        try:
            connection.execute(
                sqlalchemy.text(
                    "INSERT INTO processed (job_id, type) VALUES (:order_id, 'potions')"
                ),

                [{
                    "order_id": order_id
                }]

            )
        except IntegrityError as e:
            return "OK"
        
        # Zero everything first
        mlUsed = [0, 0, 0, 0]
        numPotMade = 0

        for pot in potions_delivered:
            potion_type = pot.potion_type

            mlUsed[0] += potion_type[0] * pot.quantity
            mlUsed[1] += potion_type[1] * pot.quantity
            mlUsed[2] += potion_type[2] * pot.quantity
            mlUsed[3] += potion_type[3] * pot.quantity

            # Update numPotMade
            numPotMade += pot.quantity

            # Update quantity in potion_inventory
            connection.execute(
                sqlalchemy.text(
                    """UPDATE potion_inventory SET quantity = quantity + :quantityBought 
                    WHERE num_red_ml = :red AND
                        num_green_ml = :green AND
                        num_blue_ml = :blue AND 
                        num_dark_ml = :dark"""
                ),
                [{
                    "quantityBought": pot.quantity,
                    "red": potion_type[0],
                    "blue": potion_type[1],
                    "green": potion_type[2],
                    "dark": potion_type[3],
                }]
            )      

        # Update ml_inventory
        totalMlUsed =  mlUsed[0] + mlUsed[1] + mlUsed[2] + mlUsed[3]
        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET total_ml = total_ml - :totalMlUsed"
            ),
            [{
                "totalMlUsed": totalMlUsed
            }]
        )
        for i in range(4):
            connection.execute(
                sqlalchemy.text(
                    "UPDATE ml_inventory SET ml = ml - :mlUsed WHERE id = :id"
                ),
                [{
                    "mlUsed":  mlUsed[i],
                    "id":  i + 1
                }]
            )

        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET total_potions =  total_potions + :numPotMade"
            ),
            [{
                "numPotMade": numPotMade
            }]
        )

    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    with db.engine.begin() as connection:
        list = []

        # Get the maxPotions I can make
        maxToMake = (connection.execute(sqlalchemy.text("SELECT pot_capacity FROM global_inventory")).scalar_one()
                      - connection.execute(sqlalchemy.text("SELECT total_potions FROM global_inventory")).scalar_one())
        numPotMade = 0

        # Make ml inventory for all colors
        mlInventory = [0, 0, 0, 0]
        for index in range(0,4):
            mlInventory[index] = connection.execute(
                sqlalchemy.text("SELECT ml FROM ml_inventory WHERE id = :id"),
                [{
                    "id": (index + 1)
                }]
            ).scalar_one()

        # Order potions by lowest quantity
        softLimit = int(connection.execute(
            sqlalchemy.text(
                "SELECT pot_capacity FROM global_inventory"
            )
        ).scalar_one() / 6)
        potionsToMake = connection.execute(
            sqlalchemy.text(
                """
                SELECT id, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml 
                FROM potion_inventory 
                WHERE quantity < :softLimit
                ORDER BY quantity 
                """
            ),
            [{
                "softLimit": softLimit
            }]
        )

        potionsToMakeAsList = []
        for p in potionsToMake:
            potionsToMakeAsList.append(
                {
                    "id": p.id,
                    "num_red_ml": p.num_red_ml,
                    "num_green_ml": p.num_green_ml,
                    "num_blue_ml": p.num_blue_ml,
                    "num_dark_ml": p.num_dark_ml
                }
            )

        
        # Place to hardcode inventory
        # mlInventory = [300, 250, 800, 0]

        # Updatable plan
        planAsDictionary = {}

        # If we don't make a potion, stop
        potionsMade = True 
        while potionsMade and (numPotMade < maxToMake):

            potionsMade = False

            # For each potion
            for p in potionsToMakeAsList:

                # If we have enough ml to make one potion
                if (mlInventory[0] >= p["num_red_ml"] and
                    mlInventory[1] >= p["num_green_ml"] and
                    mlInventory[2] >= p["num_blue_ml"] and
                    mlInventory[3] >= p["num_dark_ml"]):

                    # If it's not already in the dictionary
                    if not (p["id"] in planAsDictionary.keys()):
                        planAsDictionary[p["id"]] = 0

                    # Update amount of available ml
                    mlInventory[0] -= p["num_red_ml"]
                    mlInventory[1] -= p["num_green_ml"]
                    mlInventory[2] -= p["num_blue_ml"]
                    mlInventory[3] -= p["num_dark_ml"]

                    # Increment tracker's quantity 
                    planAsDictionary[p["id"]] += 1

                    # Quit if maxPotions
                    numPotMade += 1
                    if numPotMade >= maxToMake:
                        break

                    # Assert that we made at least one potion
                    potionsMade = True                 

        for id in planAsDictionary:
            potionTypeAsObj = connection.execute(
                sqlalchemy.text(
                    "SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM potion_inventory WHERE id = :id"
                ),
                [{
                    "id": id
                }]
            ).one()
            potionType = [0, 0, 0, 0]
            potionType[0] = potionTypeAsObj.num_red_ml
            potionType[1] = potionTypeAsObj.num_green_ml
            potionType[2] = potionTypeAsObj.num_blue_ml
            potionType[3] = potionTypeAsObj.num_dark_ml

            list.append(
                {
                    "potion_type": potionType,
                    "quantity": planAsDictionary[id]
                }
            )

    return list


if __name__ == "__main__":
    print(get_bottle_plan())