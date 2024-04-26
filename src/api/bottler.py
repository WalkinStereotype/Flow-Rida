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

        # Insert into transactions
        transaction_id = connection.execute(
            sqlalchemy.text(
                    "INSERT INTO transactions (description) VALUES ('did not set desc yet') RETURNING id"
                )
        ).scalar_one()

        # For each potion
        for pot in potions_delivered:
            potion_type = pot.potion_type

            mlUsed[0] += potion_type[0] * pot.quantity
            mlUsed[1] += potion_type[1] * pot.quantity
            mlUsed[2] += potion_type[2] * pot.quantity
            mlUsed[3] += potion_type[3] * pot.quantity

            # Update numPotMade
            numPotMade += pot.quantity

            # Add entry into potion_ledger_entries
            potion_id = connection.execute(
                sqlalchemy.text(
                    "SELECT id FROM potion_inventory WHERE potion_type = :potion_type"
                ),
                [{
                    "potion_type": potion_type
                }]
            ).scalar_one()
            connection.execute(
                sqlalchemy.text("""INSERT INTO potion_ledger_entries (transaction_id, potion_id, quantity) 
                                VALUES (:transaction_id, :potion_id, :quantity)"""),
                [{
                    "transaction_id": transaction_id,
                    "potion_id": potion_id,
                    "quantity": pot.quantity 
                }]
            )

        # Update description in transactions
        connection.execute(
            sqlalchemy.text(
                """UPDATE transactions SET description = 
                'Bottled :numPotMade potions' WHERE id = :id""" 
            ),
            [{
                "numPotMade": numPotMade,
                "id": transaction_id
            }]
        )

        # Add in ml_ledger_entries
        for i in range(0,4):
            if mlUsed[i] > 0:
                connection.execute(
                    sqlalchemy.text("""INSERT INTO ml_ledger_entries (transaction_id, barrel_id, quantity) 
                                    VALUES (:transaction_id, :barrel_id, :quantity)"""),
                    [{
                        "transaction_id": transaction_id,
                        "barrel_id": (i + 1),
                        "quantity": (mlUsed[i] * -1)
                    }]
                )
        
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    return []

    with db.engine.begin() as connection:
        list = []

        # Get the maxPotions I can make
        maxToMake = (connection.execute(sqlalchemy.text("SELECT pot_capacity FROM global_inventory")).scalar_one()
                      - connection.execute(sqlalchemy.text("SELECT total_potions FROM total_inventory_view")).scalar_one())
        numPotMade = 0

        # Make ml inventory for all colors
        mlInventory = [0, 0, 0, 0]
        for index in range(0,4):
            mlInventory[index] = connection.execute(
                sqlalchemy.text("SELECT ml FROM ml_inventory_view WHERE id = :id"),
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
                SELECT id, potion_type 
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
                    "potion_type": p.potion_type
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
                id = p["id"]
                potion_type = p["potion_type"]

                # If we have enough ml to make one potion
                if (mlInventory[0] >= potion_type[0] and
                    mlInventory[1] >= potion_type[1] and
                    mlInventory[2] >= potion_type[2] and
                    mlInventory[3] >= potion_type[3]):

                    # If it's not already in the dictionary
                    if not (id in planAsDictionary.keys()):
                        planAsDictionary[id] = 0

                    # Update amount of available ml
                    mlInventory[0] -= potion_type[0]
                    mlInventory[1] -= potion_type[1]
                    mlInventory[2] -= potion_type[2]
                    mlInventory[3] -= potion_type[3]

                    # Increment tracker's quantity 
                    planAsDictionary[id] += 1

                    # Quit if maxPotions
                    numPotMade += 1
                    if numPotMade >= maxToMake:
                        break

                    # Assert that we made at least one potion
                    potionsMade = True                 

        for id in planAsDictionary:
            potionType = connection.execute(
                sqlalchemy.text(
                    "SELECT potion_type FROM potion_inventory WHERE id = :id"
                ),
                [{
                    "id": id
                }]
            ).one()

            list.append(
                {
                    "potion_type": potionType,
                    "quantity": planAsDictionary[id]
                }
            )

    return list


if __name__ == "__main__":
    list = get_bottle_plan()

    notFirst = False

    print("Potions made: ")
    print("[")
    for p in list:
        if notFirst:
            print(f",\n\t{p["potion_type"]}: {p["quantity"]}", end = '')
        else:
            print(f"\t{p["potion_type"]}: {p["quantity"]}", end = '')
            notFirst = True
    
    print("\n]")
