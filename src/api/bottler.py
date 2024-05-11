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
    # print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    # Print barrels better
    notFirst = False
    print("Potions delievered:")
    print("[")
    for b in potions_delivered:
        if notFirst:
            print(f",\n\t{b.potion_type}: {b.quantity} potion(s)", end = '')
        else:
            print(f"\t{b.potion_type}: {b.quantity} potions(s)", end = '')
            notFirst = True
    
    print("\n]")
    print(f"order_id: {order_id}")

    # Catch any integrity errors
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
                    "INSERT INTO transactions (type, description) VALUES ('bottling', 'did not set desc yet') RETURNING id"
                )
        ).scalar_one()

        # For each potion
        for pot in potions_delivered:
            potion_type = pot.potion_type

            # Log ml used for this potion for each color
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

# DONT FORGET TO CHANGE IN CATALOG
@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    with db.engine.begin() as connection:
        list = []

        # Get the maxPotions I can make
        soft_limit_per_capacity = 10
        hard_limit_per_capacity = 6
        num_potion_type = 12

        pot_capacity = connection.execute(sqlalchemy.text("SELECT pot_capacity FROM global_inventory")).scalar_one()
        maxToMake = (pot_capacity
                      - connection.execute(sqlalchemy.text("SELECT total_potions FROM total_inventory_view")).scalar_one())
        numPotMade = 0
        softLimit = pot_capacity * soft_limit_per_capacity // 50
        hardLimit = pot_capacity * 50 // num_potion_type

        # Make ml inventory for all colors
        mlInventory = [0, 0, 0, 0]
        for index in range(0,4):
            mlInventory[index] = connection.execute(
                sqlalchemy.text("SELECT quantity FROM ml_inventory_view WHERE barrel_id = :id"),
                [{
                    "id": (index + 1)
                }]
            ).scalar_one()

        # Query all id's, potion types, and quantities
        potionsToMake = connection.execute(
            sqlalchemy.text(
                """
                SELECT potion_id, potion_type, quantity
                FROM potion_inventory_view
                WHERE NOT blacklisted
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
                    "id": p.potion_id,
                    "potion_type": p.potion_type,
                    "quantity": p.quantity,
                    "numMade" : 0
                }
            )

            # if quantity = 0 and makable
            #     take away from ml_inventory
            #     quantity += 1
            #     numMade += 1

        
        # query priority potions

        # while madeOne
        #     madeOne = false
        #     for id in priority_potions
        #         if i can make one: 
        #             take away from ml Inventory
        #             quantity += 1
        #             numMade += 1
        #             madeOne = true


        
        # Place to hardcode inventory
        # mlInventory = [300, 250, 800, 0]

        # Get min quantity as (num to start iterating from) and
        # max quality as (num to stop iterating at)
        quantTracker, maxQuant = connection.execute(sqlalchemy.text(
            """
            SELECT COALESCE(MIN(quantity), 0) AS quantTracker,
            COALESCE(MAX(quantity), 0) AS max
            FROM potion_inventory_view
            """
        )).first()

        # for p in potionsToMakeAsList:
        #     if p.quantity < min:
        #         min = p.quantity
        #     elif p.quantity > max:
        #         max = p.quantity

        # While the quantTracker has not reached the max quantity
        while quantTracker <= maxQuant and numPotMade < maxToMake:
            # For each potion
            for p in potionsToMakeAsList:
                potion_type = p["potion_type"]

                # If we have enough ml to make one potion
                if (p["quantity"] == quantTracker and
                    mlInventory[0] >= potion_type[0] and
                    mlInventory[1] >= potion_type[1] and
                    mlInventory[2] >= potion_type[2] and
                    mlInventory[3] >= potion_type[3] and 
                    p["quantity"] < hardLimit):

                    # Update amount of available ml
                    mlInventory[0] -= potion_type[0]
                    mlInventory[1] -= potion_type[1]
                    mlInventory[2] -= potion_type[2]
                    mlInventory[3] -= potion_type[3]

                    # Increment quantity and numMade of potion
                    p["quantity"] += 1
                    p["numMade"] += 1

                    # Increase maxQuant if necessary
                    if p["quantity"] > maxQuant:
                        maxQuant = p["quantity"]

                    # Quit if maxPotions
                    numPotMade += 1
                    if numPotMade >= maxToMake:
                        break 
            quantTracker += 1             

        for p in potionsToMakeAsList:
            if p["numMade"] > 0:
                list.append(
                    {
                        "potion_type": p["potion_type"],
                        "quantity": p["numMade"]
                    }
                )

    return list


if __name__ == "__main__":
    list = get_bottle_plan()

    notFirst = False

    print("Potions made: ")
    print("[")
    for p in list:
        potion_type = p["potion_type"]
        quantity = p["quantity"]
        if notFirst:
            print(f",\n\t{potion_type}: {quantity}", end = '')
        else:
            print(f"\t{potion_type}: {quantity}", end = '')
            notFirst = True
    
    print("\n]")
