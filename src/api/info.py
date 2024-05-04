import sqlalchemy
from src import database as db

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth

from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time.
    """

    print(f"Day: {timestamp.day} Hour: {timestamp.hour}")

    with db.engine.begin() as connection:
        try:
            day, hour = connection.execute(sqlalchemy.text("""WITH last_tick AS(
                    SELECT MAX(id) AS tick_id FROM ticks 
                    )
                    SELECT day, hour
                    FROM ticks JOIN last_tick ON ticks.id = last_tick.tick_id
                    LIMIT 1"""
                )
            ).fetchone()
            if (day is not timestamp.day) and (hour != timestamp.hour):
                connection.execute(
                    sqlalchemy.text(
                        "INSERT INTO ticks (day, hour) VALUES (:day, :hour)"
                    ),

                    [{
                        "day": timestamp.day,
                        "hour": timestamp.hour
                    }]

            )
        except IntegrityError as e:
            return "OK"

    return "OK"

