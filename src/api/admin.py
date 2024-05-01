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
                (pot_capacity, pot_cap_have, ml_capacity, ml_cap_have, gold_threshold_per_unit) 
                VALUES (:pot_capacity, :pot_cap_have, :ml_capacity, :ml_cap_have, :gold_threshold_per_unit)"""
            ),
            [{
                "pot_capacity": 50,
                "pot_cap_have": 1, 
                "ml_capacity": 10000, 
                "ml_cap_have": 1,
                "gold_threshold_per_unit": 3500 
            }]
        )

        # connection.execute(sqlalchemy.text("UPDATE potion_inventory SET quantity = 0"))
        # connection.execute(sqlalchemy.text("UPDATE ml_inventory SET ml = 0"))

        connection.execute(sqlalchemy.text("TRUNCATE cart_items"))
        connection.execute(sqlalchemy.text("TRUNCATE carts CASCADE"))
        connection.execute(sqlalchemy.text("TRUNCATE processed"))

        connection.execute(sqlalchemy.text("TRUNCATE potion_ledger_entries"))
        connection.execute(sqlalchemy.text("TRUNCATE gold_ledger_entries"))
        connection.execute(sqlalchemy.text("TRUNCATE ml_ledger_entries"))
        connection.execute(sqlalchemy.text("TRUNCATE transactions CASCADE"))
        connection.execute(sqlalchemy.text("TRUNCATE ticks CASCADE"))

        transaction_id = connection.execute(sqlalchemy.text(
            """INSERT INTO transactions (type, description) VALUES ('Admin', :description) RETURNING id"""),
            [{"description": "Initializing values"}]
        ).scalar()

        connection.execute(sqlalchemy.text(
                """INSERT INTO gold_ledger_entries
                (transaction_id, quantity)
                VALUES (:transaction_id, :quantity)"""
            ),
            [{
                "transaction_id": transaction_id,
                "quantity": 100
            }]
        )

        potion_ids = connection.execute(sqlalchemy.text(
            "SELECT id FROM potion_inventory"
        )).scalars()

        for id in potion_ids:
            connection.execute(sqlalchemy.text(
                    """INSERT INTO potion_ledger_entries
                    (transaction_id, potion_id, quantity)
                    VALUES (:transaction_id, :potion_id, :quantity)"""
                ),
                [{
                    "transaction_id": transaction_id,
                    "potion_id": id,
                    "quantity": 0
                }]
            )
        
        barrel_ids = connection.execute(sqlalchemy.text(
            "SELECT id FROM ml_inventory"
        )).scalars()

        for id in barrel_ids:
            connection.execute(sqlalchemy.text(
                    """INSERT INTO ml_ledger_entries
                    (transaction_id, barrel_id, quantity)
                    VALUES (:transaction_id, :barrel_id, :quantity)"""
                ),
                [{
                    "transaction_id": transaction_id,
                    "barrel_id": id,
                    "quantity": 0
                }]
            )

        

    return "OK"

