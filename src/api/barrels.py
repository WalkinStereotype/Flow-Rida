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
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    with db.engine.begin() as connection:
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
        

        for i in range(0,4):
            connection.execute(
                sqlalchemy.text("UPDATE ml_inventory SET ml = ml + :mlGained WHERE id = :id"),
                [{
                    "mlGained": mlGained[i],
                    "id": (i + 1)
                }]
            )

        connection.execute(
            sqlalchemy.text("UPDATE global_inventory SET gold = gold - :goldSpent"),
            [{
                "goldSpent": goldSpent
            }]
        )

        connection.execute(
            sqlalchemy.text("UPDATE global_inventory SET total_ml  = total_ml + :totalMl"),
            [{
                "totalMl": (
                    mlGained[0] +
                    mlGained[1] +
                    mlGained[2] +
                    mlGained[3]
                )
            }]
        )


        # LEDGERIZING
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

        for i in range(0,4):
            connection.execute(
                sqlalchemy.text("""INSERT INTO ml_ledger_entries (transaction_id, barrel_id, quantity) 
                                VALUES (:transaction_id, :barrel_id, :quantity)"""),
                [{
                    "transaction_id": transaction_id,
                    "barrel_id": (i + 1),
                    "quantity": mlGained[i]
                }]
            )


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
    print(wholesale_catalog)

    listOfSmallBarrels = {}
    listOfLargeBarrels = {}
    sumSmallPrice = 0
    hasDark = False
    hasLarge = False
    divisor = 3


    for barrel in wholesale_catalog:
        # If there are dark barrels for sale
        if(barrel.potion_type == [0, 0, 0, 1]):
            hasDark = True
        
        if(("LARGE" in barrel.sku and barrel.ml_per_barrel > 5000) or
           (barrel.ml_per_barrel >= 7500)):
            hasLarge = True

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
        # Find the amount of gold in inventory
        goldInHand = connection.execute(
            sqlalchemy.text(
                "SELECT gold FROM global_inventory"
            )
        ).scalar_one()
        
        # Place to hard code gold for testing
        # goldInHand = 10000

        goldNeeded = 0

        #List of barrels to return back
        plan = []

        # If all small barrels cannot be bought
            # PHASE 1
        if (sumSmallPrice > goldInHand):

            # Make a list of color ids by emptiness of inventory 
            smallBarrelsByNeed = connection.execute(
                sqlalchemy.text(
                    "SELECT id FROM ml_inventory ORDER BY ml, id DESC"
                )
            )
            
            # Loop through barrel ids
            for b in smallBarrelsByNeed:

                # If there is enough gold, append and update goldNeeded
                if((b.id - 1) in listOfSmallBarrels.keys() and 
                        goldInHand >= goldNeeded + listOfSmallBarrels[b.id - 1].price):
                    
                    plan.append(
                        {
                            "sku": listOfSmallBarrels[b.id - 1].sku,
                            "quantity": 1
                        }
                    )
                    goldNeeded += listOfSmallBarrels[b.id - 1].price     

        # If you have more than enough money for the small barrels
            # PHASE 2
        else:
            # Query for mlCapacity
            mlCapacity = connection.execute(
                sqlalchemy.text(
                    "SELECT ml_capacity FROM global_inventory"
                )
            ).scalar_one()

            quantitiesOfLarge = [0, 0, 0, 0]
            emptyPlan = True

            # If there are large
            if hasLarge:
                # Make a list of color ids by emptiness of inventory 
                barrel_ids = [4, 3, 2, 1]                

                divisor = 4

                boughtSomething = True
            
                while boughtSomething:
    
                    # Loop through barrel ids
                    for id in barrel_ids:
                        boughtSomething = False

                        # If there is enough gold, append and update goldInHand
                        if((id - 1) in listOfLargeBarrels.keys() and 
                                goldInHand >= listOfLargeBarrels[id - 1].price):

                            quantitiesOfLarge[id - 1] += 1
                            goldInHand -= listOfLargeBarrels[id - 1].price 
                            boughtSomething = True 
                            emptyPlan = False
                          


                for index in range(0, 4):
                    if quantitiesOfLarge[index] > 0:
                        plan.append(
                            {
                                "sku": listOfLargeBarrels[id - 1].sku,
                                "quantity": quantitiesOfLarge[index]
                            }
                        )
                        divisor -= 1


            


            # If there are dark that we haven't bought (highly unlikely)
            if hasDark:
                barrel_to_purchase = best_barrel(wholesale_catalog, goldInHand, [0, 0, 0, 1])
                total_ml = connection.execute(
                    sqlalchemy.text(
                        "SELECT total_ml FROM global_inventory"
                    )
                ).scalar_one()

                if barrel_to_purchase is not None:
                    maxToBuy = min(
                        int((mlCapacity - total_ml) / barrel_to_purchase.ml_per_barrel),
                        int(goldInHand / barrel_to_purchase.price)
                    )

                    if(maxToBuy != 0):
                        plan.append(
                            {
                                "sku": barrel_to_purchase,
                                "quantity": maxToBuy
                            }
                        )
                        emptyPlan = False


                # Query necessary attributes of color 
                colorStats = connection.execute(
                    sqlalchemy.text("SELECT id, ml, quantity_threshold, percentage_threshold FROM ml_inventory WHERE id = :barrel_id"),
                    [{
                        "barrel_id": 4
                    }]
                ).one()





                


            
            # For each color
            for i in range(0,3):
                # Query necessary attributes of color 
                colorStats = connection.execute(
                    sqlalchemy.text("SELECT id, ml, quantity_threshold, percentage_threshold FROM ml_inventory WHERE id = :barrel_id"),
                    [{
                        "barrel_id": (i + 1)
                    }]
                ).one()

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
                        quantityWanted = quant_should_buy(barrel_to_purchase, int(goldInHand / divisor), mlCapacity, colorStats)
                    else:
                        availableSpace = mlCapacity - total_ml

                        quantityWanted = min(
                            int((goldInHand / divisor) / b.price),
                            int(availableSpace * (colorStats.percentage_threshold / 100) / barrel_to_purchase.ml_per_barrel)
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
                    else: # 
                        if(int((mlCapacity * (colorStats.percentage_threshold / 100) - 
                                               colorStats.ml)) >= listOfSmallBarrels[i].price):
                            # append 
                            plan.append(
                                {
                                    "sku": listOfSmallBarrels[i].sku,
                                    "quantity": 1
                                }
                            )
                    
    return plan


def quant_should_buy(b: Barrel, gold_available: int, mlCapacity: int, colorStats):
    # Shortens name of mlPerBarrel
    mlPerBarrel = b.ml_per_barrel
            
    # This quantity is the least amount to buy to pass 
    # the threshold of 'x' times the mLPerBarrel
    quantToPassThresh = int(((mlPerBarrel * (colorStats.quantity_threshold + 1)) - 
                                colorStats.ml - 1) / mlPerBarrel)
    
    # This quantity is the most barrels I can buy without 
    # passing the capacity allotted for the color
    quantToFillCapacity = int((mlCapacity * (colorStats.percentage_threshold / 100) - 
                                colorStats.ml) / mlPerBarrel) 
    

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
