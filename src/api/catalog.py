import sqlalchemy
from src import database as db

from fastapi import APIRouter

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    # list = []
    
    with db.engine.begin() as connection:
        return [
                {
                    "sku": "GREEN_POTION_0",
                    "name": "green potion",
                    "quantity": connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 1")).scalar_one(),
                    "price": connection.execute(sqlalchemy.text("SELECT price FROM potion_inventory WHERE id = 1")).scalar_one(),
                    "potion_type": [0, 100, 0, 0],
                },
                {
                    "sku": "RED_POTION_0",
                    "name": "red potion",
                    "quantity": connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 2")).scalar_one(),
                    "price": connection.execute(sqlalchemy.text("SELECT price FROM potion_inventory WHERE id = 2")).scalar_one(),
                    "potion_type": [100, 0, 0, 0],
                },
                {
                    "sku": "BLUE_POTION_0",
                    "name": "blue potion",
                    "quantity": connection.execute(sqlalchemy.text("SELECT quantity FROM potion_inventory WHERE id = 3")).scalar_one(),
                    "price": connection.execute(sqlalchemy.text("SELECT price FROM potion_inventory WHERE id = 3")).scalar_one(),
                    "potion_type": [0, 0, 100, 0],
                }

            ]
    
    # return list
