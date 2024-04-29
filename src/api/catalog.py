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
                SUM(entries.quantity) AS quantity,
                price, 
                potion_type
            FROM potion_inventory AS potions
            LEFT JOIN potion_ledger_entries AS entries 
            ON potions.id = entries.potion_id
            GROUP BY potions.id
            ORDER BY quantity DESC
            LIMIT 6
            """
        ))

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

    print(list)
    return list


