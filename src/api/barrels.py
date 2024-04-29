import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth

from sqlalchemy.exc import IntegrityError

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

    # Print barrels better
    notFirst = False
    print("Barrels delievered:")
    print("[")
    for b in barrels_delivered:
        if notFirst:
            print(f",\n\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, price: {b.price},potion_type: {b.potion_type}, quantity: {b.quantity}", end = '')
        else:
            print(f"\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, price: {b.price}, potion_type: {b.potion_type}, quantity: {b.quantity}", end = '')
            notFirst = True
    
    print("\n]")
    print(f"order_id: {order_id}")


    with db.engine.begin() as connection:
        # Integrity Error check
        try:
            connection.execute(
                sqlalchemy.text(
                    "INSERT INTO processed (job_id, type) VALUES (:order_id, 'barrels')"
                ),

                [{
                    "order_id": order_id
                }]

            )
        except IntegrityError as e:
            return "OK"

        # Zero everything first
        mlGained = [0, 0, 0, 0]
        goldSpent = 0

        # Update mL and gold
        for b in barrels_delivered:

            if b.potion_type == [1,0,0,0]:
                mlGained[0] += b.ml_per_barrel * b.quantity 
            elif b.potion_type == [0,1,0,0]:
                mlGained[1] += b.ml_per_barrel * b.quantity 
            elif b.potion_type == [0,0,1,0]:
                mlGained[2] += b.ml_per_barrel * b.quantity 
            elif b.potion_type == [0,0,0,1]:
                mlGained[3] += b.ml_per_barrel * b.quantity 
            else:
                print("bro what\n")
                raise Exception("Invalid potion type")

            goldSpent += b.price * b.quantity

        # Insert into transactions
        transaction_id = connection.execute(
            sqlalchemy.text(
                    "INSERT INTO transactions (description) VALUES ('Purchased :totalMl ml in barrels') RETURNING id"
                ),

                [{
                    "totalMl": (
                        mlGained[0] +
                        mlGained[1] +
                        mlGained[2] +
                        mlGained[3]
                    )
                }]

        ).scalar_one()

        # Update ml_ledger_entries appropriately
        # If 0, don't update
        for i in range(0,4):
            if mlGained[i] > 0:
                connection.execute(
                    sqlalchemy.text("""INSERT INTO ml_ledger_entries (transaction_id, barrel_id, quantity) 
                                    VALUES (:transaction_id, :barrel_id, :quantity)"""),
                    [{
                        "transaction_id": transaction_id,
                        "barrel_id": (i + 1),
                        "quantity": mlGained[i]
                    }]
                )

        # Update gold_ledger_entries
        connection.execute(
                sqlalchemy.text("""INSERT INTO gold_ledger_entries (transaction_id, quantity) 
                                VALUES (:transaction_id, :quantity)"""),
                [{
                    "transaction_id": transaction_id,
                    "quantity": goldSpent * -1
                }]
            )
            
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """

    # Print barrels 2.0
    print("Catalog: ")
    notFirst = False
    print("[")
    for b in wholesale_catalog:
        if notFirst:
            print(f",\n\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, potion_type: {b.potion_type}, quantity: {b.quantity}", end = '')
        else:
            print(f"\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, potion_type: {b.potion_type}, quantity: {b.quantity}", end = '')
            notFirst = True
    
    print("\n]")


    # Place to store info of small or large barrels, if any
    listOfSmallBarrels = {}
    listOfLargeBarrels = {}

    # Variable used to declare whether in phase 1 or 2 of buying barrels
    sumSmallPrice = 0

    # For phase 2: 
    hasDark = False
    # hasLarge = False # may not be needed (if listOfLargeBarrels is empty)
    divisor = 3


    for barrel in wholesale_catalog:
        # If there are dark barrels for sale
        if(barrel.potion_type == [0, 0, 0, 1]):
            hasDark = True
        
        # If there is some sort of large barrel lmao
        if(("LARGE" in barrel.sku and barrel.ml_per_barrel > 5000) or
           (barrel.ml_per_barrel >= 7500)):
            # hasLarge = True

            # Add in barrel into list of small barrels
            for index in range(4):

                # Find the potion type of barrel
                if barrel.potion_type[index] > 0:

                    # If barrel type is already in dictionary 
                        # (niche case i will say)
                    if index in listOfLargeBarrels.keys():

                        # If the barrel's price is less than the current price
                        if barrel.price < listOfLargeBarrels[index].price:

                            # Take care of sum and update list
                            listOfLargeBarrels[index] = barrel

                    else: 
                        # If barrel type not in dictionary, add barrel
                        listOfLargeBarrels[index] = barrel

                    break

        # If there is some version of a small barrel lmao
        if (("SMALL" in barrel.sku and barrel.ml_per_barrel < 700) or 
            (barrel.ml_per_barrel >= 450 and barrel.ml_per_barrel <= 550)):
                
            # Add in barrel into list of small barrels
            for index in range(4):

                # Find the potion type of barrel
                if barrel.potion_type[index] > 0:

                    # If barrel type is already in dictionary 
                        # (niche case i will say)
                    if index in listOfSmallBarrels.keys():

                        # If the barrel's price is less than the current price
                        if barrel.price < listOfSmallBarrels[index].price:

                            # Take care of sum and update list
                            sumSmallPrice -= listOfSmallBarrels[index].price
                            listOfSmallBarrels[index] = barrel
                            sumSmallPrice += barrel.price

                    else: 
                        listOfSmallBarrels[index] = barrel
                        sumSmallPrice += barrel.price

                    break


    with db.engine.begin() as connection:

        ### VARIABLES ###

        # Find the amount of gold in inventory
        goldInHand = connection.execute(
            sqlalchemy.text(
                "SELECT gold FROM total_inventory_view"
            )
        ).scalar_one()
        
        # Place to hard code gold for testing
        # goldInHand = 10000

        #List of barrels to return back
        plan = []


        ### WE BALL, THIS IS THE BALLING PLAN ###

        # If all small barrels cannot be bought
            # PHASE 1
        if (sumSmallPrice > goldInHand):
            # Variable of how much gold spent so far
            goldNeeded = 0

            # Make a list of color ids by emptiness of inventory 
            smallBarrelsByNeed = connection.execute(
                sqlalchemy.text(
                    "SELECT barrel_id FROM ml_inventory_view ORDER BY quantity, barrel_id DESC"
                )
            ).scalars()
            
            # Loop through barrel ids
            for id in smallBarrelsByNeed:

                # If there is enough gold, append and update goldNeeded
                if((id - 1) in listOfSmallBarrels.keys() and 
                        goldInHand >= goldNeeded + listOfSmallBarrels[id - 1].price):
                    
                    plan.append(
                        {
                            "sku": listOfSmallBarrels[id - 1].sku,
                            "quantity": 1
                        }
                    )
                    goldNeeded += listOfSmallBarrels[id - 1].price     

        # If you have more than enough money for the small barrels
            # PHASE 2
        else:
            # Query for mlCapacity
            mlCapacity = connection.execute(
                sqlalchemy.text(
                    "SELECT ml_capacity FROM global_inventory"
                )
            ).scalar_one()

            # Checks for plan length
            emptyPlan = True

            quantitiesOfLarge = [0, 0, 0, 0]

            # If there are large
            if listOfLargeBarrels:
                
                # Make a list of color ids by emptiness of inventory 
                barrel_ids = [4, 3, 2, 1]                

                divisor = 4

                boughtSomething = True
            
                while boughtSomething:
                    boughtSomething = False
    
                    # Loop through barrel ids
                    for id in barrel_ids:
                        # If there is enough gold, append and update goldInHand
                        if((id - 1) in listOfLargeBarrels.keys() and 
                                goldInHand >= listOfLargeBarrels[id - 1].price):

                            quantitiesOfLarge[id - 1] += 1
                            goldInHand -= listOfLargeBarrels[id - 1].price 
                            boughtSomething = True 
                            emptyPlan = False
                          


                for id in barrel_ids:
                    if quantitiesOfLarge[id - 1] > 0:
                        plan.append(
                            {
                                "sku": listOfLargeBarrels[id - 1].sku,
                                "quantity": quantitiesOfLarge[id - 1]
                            }
                        )
                        divisor -= 1


            


            # If there are dark that we haven't bought (highly unlikely)
            if hasDark:
                # Find best barrel and get current amount of ml
                barrel_to_purchase = best_barrel(wholesale_catalog, goldInHand, [0, 0, 0, 1])
                total_ml = connection.execute(
                    sqlalchemy.text(
                        "SELECT total_ml FROM total_inventory_view"
                    )
                ).scalar_one()

                if barrel_to_purchase is not None:
                    maxToBuy = min(
                        int((mlCapacity - total_ml) / barrel_to_purchase.ml_per_barrel),
                        int(goldInHand / barrel_to_purchase.price),
                        barrel_to_purchase.quantity
                    )

                    if(maxToBuy != 0):
                        plan.append(
                            {
                                "sku": barrel_to_purchase,
                                "quantity": maxToBuy
                            }
                        )
                        emptyPlan = False
                        goldInHand -= maxToBuy * barrel_to_purchase.price
           
            # Niche handling:
                # If we didn't buy at least one barrel at this point 
                    # Despite seeing large and/or dark barrels in stock:
                # Set the divisor of gold back to 3
            if divisor > 3:
                divisor = 3

            # For each color
            for i in range(0,3):
                if quantitiesOfLarge[i] == 0:
                    # Query necessary attributes of color 
                    colorStats = connection.execute(
                        sqlalchemy.text("SELECT id, ml, quantity_threshold, percentage_threshold FROM ml_inventory WHERE id = :barrel_id"),
                        [{
                            "barrel_id": (i + 1)
                        }]
                    ).one()
                    colorMl = connection.execute(
                        sqlalchemy.text("SELECT quantity FROM ml_inventory_view WHERE barrel_id = :barrel_id"),
                        [{
                            "barrel_id": (i + 1)
                        }]
                    ).scalar_one()

                    # Finds barrel type based on i index
                    potion_type_wanted = [int(j == i) for j in range(4)]

                    # Find best type of barrel to purchase for that color
                    barrel_to_purchase = best_barrel(wholesale_catalog, 
                                                    int(goldInHand / divisor), 
                                                    potion_type_wanted)
                    
                    # If there is a barrel to purchase (should always happen)
                    if(barrel_to_purchase is not None):

                        # Use weird algorithm to find how many barrels to buy
                        if emptyPlan:
                            quantityWanted = quant_should_buy(barrel_to_purchase, int(goldInHand / divisor), mlCapacity, colorStats, colorMl)
                        else:
                            availableSpace = mlCapacity - total_ml

                            quantityWanted = min(
                                int((goldInHand / divisor) / b.price),
                                int(availableSpace * (colorStats.percentage_threshold / 100) / barrel_to_purchase.ml_per_barrel),
                                barrel_to_purchase.quantity
                            )
                        
                        # Don't add if one constraint prohibits us from buying
                        if(quantityWanted != 0):

                            # append 
                            plan.append(
                                {
                                    "sku": barrel_to_purchase.sku,
                                    "quantity": quantityWanted
                                }
                            )
                    
    return plan


def quant_should_buy(b: Barrel, gold_available: int, mlCapacity: int, colorStats, colorMl: int):
    # Shortens name of mlPerBarrel
    mlPerBarrel = b.ml_per_barrel
            
    # This quantity is the least amount to buy to pass 
    # the threshold of 'x' times the mLPerBarrel
    quantToPassThresh = int(((mlPerBarrel * (colorStats.quantity_threshold + 1)) - 
                                colorMl - 1) / mlPerBarrel)
    
    # This quantity is the most barrels I can buy without 
    # passing the capacity allotted for the color
    quantToFillCapacity = int((mlCapacity * (colorStats.percentage_threshold / 100) - 
                                colorMl) / mlPerBarrel) 
    

    # Choose the min between:
        # amount that can be bought by the gold
        # amount constrained by the max I think I should buy
        # amount constrained by the capacity allotted for the color
        # amount available by the catalog
    return min(
        int((gold_available) / b.price),
        quantToPassThresh,
        quantToFillCapacity,
        b.quantity
    )




def best_barrel(wholesale_catalog: list[Barrel], gold_available: int, potion_type):
    best = None
    maxRatio = 0
    current_ml_per_barrel = 0
    for b in wholesale_catalog:
        assign = False

        # if this is the color wanted
        if (b.potion_type == potion_type): 

            # if there is enough money to buy at least one
            if (b.price <= gold_available): 

                # if the barrel is cheaper per ml
                if(b.ml_per_barrel / b.price > maxRatio): 
                    assign = True
                
                # else if the barrel's ratio is the same but is a bigger size
                elif (b.ml_per_barrel / b.price == maxRatio and 
                        b.ml_per_barrel > current_ml_per_barrel):
                    assign = True
        
        if assign:
            best = b
            current_ml_per_barrel = b.ml_per_barrel
            maxRatio = b.ml_per_barrel / b.price
    
    return best
