import sqlalchemy
from src import database as db

from fastapi import APIRouter

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    
    with db.engine.begin() as connection:
        numGreenPotions = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory"))

    return [
            {
                "sku": "GREEN_POTION_0",
                "name": "green potion",
                "quantity": numGreenPotions,
                "price": 50,
                "potion_type": [0, 100, 0, 0],
            }
        ]
