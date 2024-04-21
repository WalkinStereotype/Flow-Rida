import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("TRUNCATE global_inventory"))
        connection.execute(
            sqlalchemy.text(
                """INSERT INTO global_inventory 
                (gold, total_potions, pot_capacity, pot_cap_have, total_ml, ml_capacity, ml_cap_have) 
                VALUES (:gold, :total_potions, :pot_capacity, :pot_cap_have, :total_ml, :ml_capacity, :ml_cap_have)"""
            ),
            [{
                "gold": 100, 
                "total_potions": 0, 
                "pot_capacity": 50,
                "pot_cap_have": 1, 
                "total_ml": 0, 
                "ml_capacity": 10000, 
                "ml_cap_have": 1
            }]
        )

        connection.execute(sqlalchemy.text("UPDATE potion_inventory SET quantity = 0"))
        connection.execute(sqlalchemy.text("UPDATE ml_inventory SET ml = 0"))

        connection.execute(sqlalchemy.text("TRUNCATE cart_items"))
        connection.execute(sqlalchemy.text("TRUNCATE carts CASCADE"))
        connection.execute(sqlalchemy.text("TRUNCATE processed"))

    return "OK"

