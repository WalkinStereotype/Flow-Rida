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
            print(f",\n\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, price: {b.price}, potion_type: {b.potion_type}, quantity: {b.quantity}", end = '')
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
                    "INSERT INTO transactions (type, description) VALUES ('barrel purchasing', 'Purchased :totalMl ml in barrels') RETURNING id"
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
    print("Barrel catalog: ")
    notFirst = False
    print("[")
    for b in wholesale_catalog:
        if notFirst:
            print(f",\n\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, potion_type: {b.potion_type}, price: {b.price}, quantity: {b.quantity}", end = '')
        else:
            print(f"\t{b.sku}:\n\t\tml: {b.ml_per_barrel}, potion_type: {b.potion_type}, price: {b.price}, quantity: {b.quantity}", end = '')
            notFirst = True
    
    print("\n]")

    with db.engine.begin() as connection:
        # Boolean variables (there should always be small?)
        mediumPresent = False
        largePresent = False
        sumSmallPrice = 0

        # Query gold and necessary details for each color
        goldInHand, totalMl = connection.execute(sqlalchemy.text(
            "SELECT gold, total_ml FROM total_inventory_view"
        )).fetchone()
        availableSpace = (connection.execute(sqlalchemy.text("SELECT ml_capacity FROM global_inventory")).scalar_one() 
                          - totalMl)
        colorStatsList = connection.execute(sqlalchemy.text(
            """
            SELECT
                id, 
                barrels.color,
                barrel_quantities.quantity,
                barrels.reg_threshold,
                barrels.large_threshold
            FROM ml_inventory AS barrels
            JOIN ml_inventory_view AS barrel_quantities
            ON barrels.id = barrel_quantities.barrel_id
            ORDER BY barrel_quantities.quantity, barrels.id DESC
            """
        )).fetchall()

        # organizedCatalog = {
        #     "red": [],
        #     "green":[],
        #     "blue": [],
        #     "dark": []
        # }

        organizedCatalog = {
            "small": {},
            "medium": {},
            "large": {}
        }

        # Find any small, medium, large
        for b in wholesale_catalog:
            color = ""
            size = ""
            match b.potion_type:
                case [1, 0, 0, 0]:
                    color = "red"
                case [0, 1, 0, 0]:
                    color = "green"
                case [0, 0, 1, 0]:
                    color = "blue"
                case [0, 0, 0, 1]:
                    color = "dark"
                case _:
                    print("bro HUH?")
                    continue
            
            if "SMALL" in b.sku:
                if b.potion_type == [0, 0, 0, 1]:
                    continue
                if sumSmallPrice < b.price:
                    sumSmallPrice = b.price
                size = "small"
            elif "MEDIUM" in b.sku:
                size = "medium"
                mediumPresent = True
            elif "LARGE" in b.sku:
                size = "large"
                largePresent = True
            else:
                continue

            organizedCatalog[size][color] = b

    ### VARIABLES ###
        
        # Place to hard code gold for testing
        # goldInHand = 10000

        #List of barrels to return back
        plan = []
        sumSmallPrice *= 3


        ### WE BALL, THIS IS THE BALLING PLAN ###

        # If all small barrels cannot be bought
            # PHASE 1
        if (sumSmallPrice > goldInHand):
            # Variable of how much gold spent so far
            goldNeeded = 0

            # if mediumPresent:
            #     for colorStats in colorStatsList:
            #         color = colorStats[1]
            #         if(color in organizedCatalog["medium"].keys() and 
            #                 goldInHand >= goldNeeded + organizedCatalog["medium"][color].price and
            #                 availableSpace >= organizedCatalog["medium"][color].ml_per_barrel):
                    
            #             plan.append(
            #                 {
            #                     "sku": organizedCatalog["medium"][color].sku,
            #                     "quantity": 1
            #                 }
            #             )
            #             goldNeeded += organizedCatalog["medium"][color].price 
            #             availableSpace -= organizedCatalog["medium"][color].ml_per_barrel


            
            # Loop through barrel ids
            for colorStats in colorStatsList:
                color = colorStats[1]

                # If there is enough gold, append and update goldNeeded
                if(color in organizedCatalog["small"].keys() and 
                        goldInHand >= goldNeeded + organizedCatalog["small"][color].price and
                        availableSpace >= organizedCatalog["small"][color].ml_per_barrel):
                    
                    plan.append(
                        {
                            "sku": organizedCatalog["small"][color].sku,
                            "quantity": 1
                        }
                    )
                    goldNeeded += organizedCatalog["small"][color].price 
                    availableSpace -= organizedCatalog["small"][color].ml_per_barrel

        # If you have more than enough money for the small barrels
            # PHASE 2
        else:

            largeQuantities = {
                "red": 0,
                "green": 0,
                "blue": 0,
                "dark": 0
            }

            if largePresent:
                largeBarrels = organizedCatalog["large"]
                stillBuying = True

                while stillBuying:
                    stillBuying = False

                    for colorStats in colorStatsList:
                        color = colorStats[1]

                        if(color in largeBarrels.keys() and 
                            goldInHand >= largeBarrels[color].price and
                            colorStats.quantity + largeBarrels[color].ml_per_barrel <= colorStats.large_threshold and
                            availableSpace >= largeBarrels[color].ml_per_barrel):

                            goldInHand -= largeBarrels[color].price
                            largeQuantities[color] += 1
                            availableSpace -= largeBarrels[color.ml_per_barrel]
                            stillBuying = True
            
            for colorStats in colorStatsList:
                color = colorStats[1]

                if largeQuantities[color] > 0:
                    plan.append(
                        {
                            "sku": organizedCatalog["large"][color].sku,
                            "quantity": largeQuantities[color]
                        }
                    )
                else:
                    if color == "dark":
                        continue
                    
                    if (mediumPresent and (goldInHand // 3) >= organizedCatalog["medium"][color].price and
                        availableSpace >= organizedCatalog["medium"][color].ml_per_barrel):

                        mediumBarrel = organizedCatalog["medium"][color]
                        
                        if (colorStats.quantity + mediumBarrel.ml_per_barrel <= colorStats.reg_threshold):
                            quantityToBuy = min(
                                mediumBarrel.quantity,
                                (goldInHand // 3) // mediumBarrel.price,
                                (colorStats.reg_threshold - colorStats.quantity) // mediumBarrel.ml_per_barrel,
                                availableSpace // mediumBarrel.ml_per_barrel
                            )

                            if quantityToBuy > 0:
                                plan.append(
                                    {
                                        "sku": mediumBarrel.sku,
                                        "quantity": quantityToBuy
                                    }
                                )
                                availableSpace -= (mediumBarrel.ml_per_barrel * quantityToBuy)
                        else: 
                            print("enough gold for medium but not enough space")

                    else:
                        if (color in organizedCatalog["small"].keys() and 
                            (goldInHand // 3) >= organizedCatalog["small"][color].price and
                            availableSpace >= organizedCatalog["small"][color].ml_per_barrel):

                            smallBarrel = organizedCatalog["small"][color]
                            quantityToBuy = min(
                                smallBarrel.quantity,
                                (goldInHand // 3) // smallBarrel.price,
                                (colorStats.reg_threshold // 2 - colorStats.quantity) // smallBarrel.ml_per_barrel,
                                availableSpace // smallBarrel.ml_per_barrel,

                            )

                            if quantityToBuy > 0:
                                plan.append(
                                    {
                                        "sku": smallBarrel.sku,
                                        "quantity": quantityToBuy
                                    }
                                )
                                availableSpace -= (smallBarrel.ml_per_barrel * quantityToBuy)
                
        return plan

                                

                        


# phase 2:
#     if there are large:
#         if large barrel size <= large color threshold and (enough gold):
#             buy as many as you can
#     for each color in rgb:
#         if large barrel of that color hasnt been bought:
#             if medium exists:
#                 if medium barrel size <= reg_threshold - color_capacity and (enough gold)
#                     buy as much as you can without going over reg_threshold
#                 else:
#                     try to buy only one small Barrel
#             else:
#                 try to buy as many small barrels as possible




        
                


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
