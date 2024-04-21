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
        
        table = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory ORDER BY quantity DESC"))
        numInCatalog = 0

        for potion in table:
            if potion.quantity > 0:
                list.append(
                    {
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity,
                        "price": potion.price,
                        "potion_type": [
                            potion.num_red_ml, 
                            potion.num_green_ml, 
                            potion.num_blue_ml, 
                            potion.num_dark_ml
                        ]
                    }
                )
                numInCatalog += 1
                if numInCatalog == 6:
                    break

    return list


