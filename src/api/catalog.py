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
        day, hour = connection.execute(sqlalchemy.text(
            """
            WITH max_id AS(
            SELECT MAX(id) AS last_id
            FROM ticks
            )
            SELECT day, hour
            FROM max_id 
            JOIN ticks
            ON max_id.last_id = ticks.id
            LIMIT 1
            """ 
        )).fetchone()
        print(f"day: {day}, hour: {hour}")
        
        table = connection.execute(
            sqlalchemy.text(
                """
                select 
                    subquery3.potion_id,
                    sum_purchases_on_hour,
                    sum_purchases_on_day, 
                    sum_purchases_general,
                    rn,
                    sku,
                    name,
                    price,
                    potion_type,
                    quantity

                from
                (select *,
                    row_number() over (
                        order by 
                        sum_purchases_on_hour desc,
                        sum_purchases_on_day desc,
                        sum_purchases_general desc
                    ) as rn
                from
                    (select 
                    subquery.potion_id, 
                    coalesce(sum(case
                        when ticks.day = :day and ticks.hour = :hour and quantity < 0 then quantity * -1
                        else 0 end
                        ), 0) as sum_purchases_on_hour,
                    coalesce(sum(case 
                        when ticks.day = :day and quantity < 0 then quantity * -1
                        else 0 end
                        ), 0) as sum_purchases_on_day,
                    coalesce(sum(case
                        when quantity < 0 then quantity * -1
                        else 0 end
                        ), 0) as sum_purchases_general
                    from 
                        (select potion_id
                        from potion_inventory_view
                        where quantity > 0) as subquery

                    join potion_ledger_entries as entries
                    on subquery.potion_id = entries.potion_id
                    left join ticks
                    on entries.tick_id = ticks.id
                    group by subquery.potion_id
                    ) as subquery2
                order by 
                    case 
                    when sum_purchases_general > 0 then 1
                    else 1 + random() end,
                    sum_purchases_on_hour desc,
                    sum_purchases_on_day desc,
                    sum_purchases_general desc
                ) as subquery3
                join potion_inventory_view as potions 
                on potions.potion_id = subquery3.potion_id
                order by 
                case
                    when rn <= 5 then rn
                    else 5 + random() end
                limit 6
                """
            ),
            [{
                "day": day,
                "hour": hour
            }]
        )
            # GROUP BY potions.id
            # ORDER BY quantity DESC

        for potion in table:
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



