import sqlalchemy
from src import database as db

from fastapi import APIRouter

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    potionsToBeMade = get_bottle_plan()
    addedQuantities = {}

    list = []
    
    with db.engine.begin() as connection:

        for pot in potionsToBeMade:
            potion_type = pot["potion_type"]

            # Add entry into potion_ledger_entries
            potion_sku = connection.execute(
                sqlalchemy.text(
                    "SELECT sku FROM potion_inventory WHERE potion_type = :potion_type"
                ),
                [{
                    "potion_type": potion_type
                }]
            ).scalar_one()

            addedQuantities[potion_sku] = pot["quantity"]


        day, hour = connection.execute(sqlalchemy.text(
            """
            WITH max_id AS(
            SELECT MAX(id) AS last_id
            FROM ticks
            )
            SELECT day, hour
            FROM max_id 
            JOIN ticks
            ON max_id.last_id = ticks.id
            LIMIT 1
            """ 
        )).fetchone()
        print(f"day: {day}, hour: {hour}")

        # Is it night for the rogues? (Hours 0-6)
        isNight = False
        # if (hour >= 0) and (hour <= 6):
        #     isNight = True
        
        
        # table = connection.execute(
        #     sqlalchemy.text(
        #         """
        #         select 
        #             subquery3.potion_id,
        #             sum_purchases_on_hour,
        #             sum_purchases_on_day, 
        #             sum_purchases_general,
        #             rn,
        #             sku,
        #             name,
        #             price,
        #             potion_type,
        #             quantity

        #         from
        #         (select *,
        #             row_number() over (
        #                 order by 
        #                 sum_purchases_on_hour desc,
        #                 sum_purchases_on_day desc,
        #                 sum_purchases_general desc
        #             ) as rn
        #         from
        #             (select 
        #             entries.potion_id, 
        #             coalesce(sum(case
        #                 when ticks.day = :day and ticks.hour = :hour and quantity < 0 then quantity * -1
        #                 else 0 end
        #                 ), 0) as sum_purchases_on_hour,
        #             coalesce(sum(case 
        #                 when ticks.day = :day and quantity < 0 then quantity * -1
        #                 else 0 end
        #                 ), 0) as sum_purchases_on_day,
        #             coalesce(sum(case
        #                 when quantity < 0 then quantity * -1
        #                 else 0 end
        #                 ), 0) as sum_purchases_general
        #             from potion_ledger_entries as entries
        #             left join ticks
        #             on entries.tick_id = ticks.id
        #             group by entries.potion_id
        #             ) as subquery2
        #         order by 
        #             case 
        #             when sum_purchases_on_day > 0 then 1
        #             else 1 + random() end,
        #             sum_purchases_on_hour desc,
        #             sum_purchases_on_day desc
        #         ) as subquery3
        #         join potion_inventory_view as potions 
        #         on potions.potion_id = subquery3.potion_id
        #         order by 
        #         case
        #             when rn <= 5 then rn
        #             else 6 + random() end
        #         """
        #     ),
        #     [{
        #         "day": day,
        #         "hour": hour
        #     }]
        # )
            # GROUP BY potions.id
            # ORDER BY quantity DESC

        table = connection.execute(
            sqlalchemy.text(
                """
                select 
                    potion_id,
                    sku,
                    name,
                    quantity,
                    price,
                    potion_type
                from temp_catalog_view
                """
            )
        )


        counter = 0

        for potion in table:
            numMade = 0
            if potion.sku in addedQuantities.keys():
                numMade = addedQuantities[potion.sku]
            

            if potion.quantity + numMade > 0 and ((isNight and counter < 5) or ((not isNight) and counter < 6)):

                list.append(
                    {
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity + numMade,
                        "price": potion.price,
                        "potion_type": potion.potion_type
                    }
                )


                counter += 1  

            elif potion.potion_type == [0, 0, 0, 100] and potion.quantity + numMade > 0:
                list.append(
                    {
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity + numMade,
                        "price": potion.price,
                        "potion_type": potion.potion_type
                    }
                )
                counter += 1 

            if counter >= 6:
                break

    # print(list)

    # Print catalog 2.0
    print("My catalog: ")
    notFirst = False
    print("[")
    for p in list:
        if notFirst:
            print(f",\n\t{p['sku']} ({p['name']}):\n\t\tquantity: {p['quantity']}, price: {p['price']}, potion_type: {p['potion_type']}", end = '')
        else:
            print(f"\t{p['sku']} ({p['name']}):\n\t\tquantity: {p['quantity']}, price: {p['price']}, potion_type: {p['potion_type']}", end = '')
            notFirst = True
    
    print("\n]")
    return list

# DONT FORGET TO CHANGE IN BOTTLER
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



