import sqlalchemy
from src import database as db

from fastapi import APIRouter

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    list = []
    
    with db.engine.begin() as connection:
        
        table = connection.execute(sqlalchemy.text(
            """
            SELECT 
                potions.id AS id, 
                sku,
                name, 
                COALESCE(SUM(entries.quantity), 0) AS quantity,
                price, 
                potion_type
            FROM potion_inventory AS potions
            LEFT JOIN potion_ledger_entries AS entries 
            ON potions.id = entries.potion_id
            WHERE quantity > 0
            GROUP BY potions.id
            ORDER BY RANDOM()
            LIMIT 6
            """
        ))
            # GROUP BY potions.id
            # ORDER BY quantity DESC

        for potion in table:
            if potion.quantity is None:
                continue
            if potion.quantity > 0:
                list.append(
                    {
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity,
                        "price": potion.price,
                        "potion_type": potion.potion_type
                    }
                )

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


