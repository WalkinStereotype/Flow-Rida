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
        x = connection.execute(
            sqlalchemy.text(
                """SELECT 
                    total_potions, 
                    total_ml, 
                    gold 
                FROM total_inventory_view"""
            )
        ).one()
    print(f"number of potions: {x.total_potions}, ml_in_barrels: {x.total_ml}, gold: {x.gold}")
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
        x = connection.execute(sqlalchemy.text(
            """
            SELECT 
                pot_capacity, pot_cap_have, pot_percentage_thresh, 
                ml_capacity, ml_cap_have, ml_percentage_thresh,
                gold_threshold_per_unit
            FROM global_inventory
            """
        )).one()
        resultFromView = connection.execute(
            sqlalchemy.text(
                "SELECT gold, total_ml, total_potions FROM total_inventory_view"
            )
        ).one()

        manualPlan = connection.execute(
            sqlalchemy.text(
                """
                SELECT ml_cap_to_buy, pot_cap_to_buy, gold_required FROM capacity_plan
                """
            )
        ).one()

        if((manualPlan.ml_cap_to_buy > 0 or manualPlan.pot_cap_to_buy > 0) and 
                resultFromView.gold > manualPlan.gold_required + ((manualPlan.ml_cap_to_buy + manualPlan.pot_cap_to_buy) * 1000)):
            
            ml_capacity_manual = manualPlan.ml_cap_to_buy
            potion_capacity_manual = manualPlan.pot_cap_to_buy

            connection.execute(
                sqlalchemy.text(
                    """
                    UPDATE capacity_plan 
                    SET ml_cap_to_buy = 0, pot_cap_to_buy = 0
                    """
                )
            )
            
            return {
                "potion_capacity": potion_capacity_manual,
                "ml_capacity": ml_capacity_manual
            }

        goldThresholdPot = x.pot_cap_have * x.gold_threshold_per_unit
        goldThresholdMl = x.ml_cap_have * x.gold_threshold_per_unit

        if ((resultFromView.gold >= goldThresholdPot) and 
            (resultFromView.total_potions >= int(x.pot_capacity * x.pot_percentage_thresh / 100)) and
            (x.pot_cap_have < x.ml_cap_have + 2)):

            potion_capacity += 1
            goldThresholdMl - 1000

        if  ((resultFromView.gold >= goldThresholdMl) and  
            (resultFromView.total_ml >= int(x.ml_capacity * x.ml_percentage_thresh / 100)) and
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

            # LEDGERIZING
            transaction_id = connection.execute(
                sqlalchemy.text(
                    "INSERT INTO transactions (type, description) VALUES ('capacity purchasing', 'Purchased :ml_cap ml_capacity and :pot_cap pot_capacity') RETURNING id"
                ),
                [{
                    "ml_cap": capacity_purchase.ml_capacity,
                    "pot_cap": capacity_purchase.potion_capacity
                }]
            ).scalar_one()
        except IntegrityError as e:
            return "OK"

        
        #  LEDGERIZING AGAIN
        connection.execute(
            sqlalchemy.text(
                "INSERT INTO gold_ledger_entries (transaction_id, quantity) VALUES (:transaction_id, :quantity)"
            ),
            [{
                "transaction_id": transaction_id,
                "quantity": ((capacity_purchase.potion_capacity + capacity_purchase.ml_capacity) * -1000)
            }]
        )
    
        ml_cap_have = connection.execute(
            sqlalchemy.text(
                """
                UPDATE global_inventory 
                SET pot_capacity = pot_capacity + :potion_capacity * 50,
                pot_cap_have = pot_cap_have + :potion_capacity,
                ml_capacity = ml_capacity + :ml_capacity * 10000,
                ml_cap_have = ml_cap_have + :ml_capacity
                RETURNING ml_cap_have
                """
            ),
            [{
                "potion_capacity": capacity_purchase.potion_capacity,
                "ml_capacity": capacity_purchase.ml_capacity
            }]
        ).scalar_one()
        print(f"ml_cap_have afteer change: {ml_cap_have}")

        # Updating thresholds
        ml_capacity = connection.execute(
            sqlalchemy.text(
                "SELECT ml_capacity FROM global_inventory"
            )
        ).scalar_one()

        if ml_capacity <= 60000:
            x = connection.execute(
                sqlalchemy.text(
                    """
                    SELECT 
                        reg_red_threshold,
                        large_red_threshold,
                        reg_green_threshold,
                        large_green_threshold,
                        reg_blue_threshold,
                        large_blue_threshold,
                        large_dark_threshold
                    FROM ml_thresholds
                    WHERE ml_capacity = :ml_capacity
                    """
                ),
                [{
                    "ml_capacity": ml_capacity
                }]
            ).fetchone()

            thresholds = {
                "reg": {
                    "red": x[0],
                    "green": x[2],
                    "blue": x[4],
                    "dark": x[6]
                },
                "large": {
                    "red": x[1],
                    "green": x[3],
                    "blue": x[5],
                    "dark": x[6]
                }
            }

            for color in ["red", "green", "blue", "dark"]:
                connection.execute(
                    sqlalchemy.text(
                        """
                        UPDATE ml_inventory
                        SET reg_threshold = :reg,
                        large_threshold = :large
                        WHERE color = :color
                        """
                    ),
                    [{
                        "reg": thresholds["reg"][color],
                        "large": thresholds["large"][color],
                        "color": color
                    }]
                )

        else:
            connection.execute(
                sqlalchemy.text(
                    """
                    UPDATE ml_inventory 
                    SET reg_threshold = :ml_cap * 1250,
                    large_threshold = :ml_cap * 2500
                    """
                ), 
                [{
                    "ml_cap": ml_cap_have
                }]
            )
    print(f"")
    return "OK"
