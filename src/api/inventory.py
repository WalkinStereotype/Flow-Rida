import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math

from sqlalchemy.exc import IntegrityError


router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """

    with db.engine.begin() as connection:
        x = connection.execute(sqlalchemy.text("SELECT total_potions, total_ml, gold FROM global_inventory")).one()
    return {"number_of_potions": x.total_potions, "ml_in_barrels": x.total_ml, "gold": x.gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    potion_capacity = 0
    ml_capacity = 0

    with db.engine.begin() as connection:
        x = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).one()

        goldThresholdPot = x.pot_cap_have * x.gold_threshold_per_unit
        goldThresholdMl = x.ml_cap_have * x.gold_threshold_per_unit

        if ((x.gold >= goldThresholdPot) and 
            (x.total_potions >= int(x.pot_capacity * x.pot_percentage_thresh / 100)) and
            (x.pot_cap_have < x.ml_cap_have + 2)):

            potion_capacity += 1
            goldThresholdMl - 1000

        if  ((x.gold >= goldThresholdMl) and  
            (x.total_ml >= int(x.ml_capacity * x.ml_percentage_thresh / 100)) and
            (x.ml_cap_have <= x.pot_cap_have)):

            ml_capacity += 1

    return {
        "potion_capacity": potion_capacity,
        "ml_capacity": ml_capacity
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    with db.engine.begin() as connection:
        try:
            connection.execute(
                sqlalchemy.text(
                    "INSERT INTO processed (job_id, type) VALUES (:order_id, 'capacities')"
                ),

                [{
                    "order_id": order_id
                }]

            )
        except IntegrityError as e:
            return "OK"
    
        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET pot_capacity = pot_capacity + :potion_capacity * 50"
            ),
            [{
                "potion_capacity": capacity_purchase.potion_capacity
            }]
        )
        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET pot_cap_have = pot_cap_have + :potion_capacity"
            ),
            [{
                "potion_capacity": capacity_purchase.potion_capacity
            }]
        )
        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET ml_capacity = ml_capacity + :ml_capacity * 10000"
            ),
            [{
                "potion_capacity": capacity_purchase.potion_capacity
            }]
        )
        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET ml_cap_have = ml_cap_have + :ml_capacity"
            ),
            [{
                "potion_capacity": capacity_purchase.potion_capacity
            }]
        )
    

    return "OK"
