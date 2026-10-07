DEFAULT_COSTS = {
    "transport_per_km": 12.0,
    "food_per_person_per_day": 500.0,
    "accommodation_per_person_per_day": 1000.0,
    "entry_fee_buffer": 0.0,
    "miscellaneous_per_day": 200.0,
}


def calculate_cab_transport_cost(
    distance_km,
    days=1,
    budget_level="standard",
    travelers=1,
):
    """Estimate a tourist cab using a day-package model.

    This intentionally does not claim a universal per-km taxi fare.
    It uses an indicative vehicle package with included km/day, then adds
    extra-km charges and driver allowance. Toll, parking and surge/peak
    charges are not included because they vary by operator and route.
    """
    try:
        distance_km = max(0.0, float(distance_km))
        days = max(1, int(days))
        travelers = max(1, int(travelers))
    except (TypeError, ValueError):
        return {"cost": 0.0, "vehicle": "Sedan", "vehicles": 1, "extra_km": 0.0}

    from .cost_rules import COST_RULES, BUDGET_LEVELS

    if budget_level not in BUDGET_LEVELS:
        budget_level = "standard"

    package = COST_RULES["transport_package"][budget_level]
    capacity = int(package["capacity"])
    vehicles = max(1, (travelers + capacity - 1) // capacity)

    included_km = float(package["included_km_per_day"]) * days
    extra_km = max(0.0, distance_km - included_km)

    base = float(package["base_per_day"]) * days
    driver = float(package["driver_allowance_per_day"]) * days
    extra = extra_km * float(package["extra_km_rate"])

    cost = (base + driver + extra) * vehicles

    return {
        "cost": round(cost, 2),
        "vehicle": package["vehicle"],
        "vehicles": vehicles,
        "included_km": round(included_km, 2),
        "extra_km": round(extra_km, 2),
        "base_package": round(base * vehicles, 2),
        "driver_allowance": round(driver * vehicles, 2),
        "extra_km_charge": round(extra * vehicles, 2),
    }


def calculate_transport_cost(
    distance_km,
    transport_cost_per_km=None,
):
    try:
        distance_km = float(distance_km)
    except (TypeError, ValueError):
        return 0.0

    if transport_cost_per_km is None:
        transport_cost_per_km = DEFAULT_COSTS[
            "transport_per_km"
        ]

    try:
        transport_cost_per_km = float(
            transport_cost_per_km
        )
    except (TypeError, ValueError):
        return 0.0

    return round(
        max(0, distance_km)
        * max(0, transport_cost_per_km),
        2,
    )


def calculate_food_cost(
    travelers,
    days,
    cost_per_person_per_day=None,
):
    try:
        travelers = max(1, int(travelers))
        days = max(1, int(days))
    except (TypeError, ValueError):
        return 0.0

    if cost_per_person_per_day is None:
        cost_per_person_per_day = DEFAULT_COSTS[
            "food_per_person_per_day"
        ]

    try:
        cost_per_person_per_day = float(
            cost_per_person_per_day
        )
    except (TypeError, ValueError):
        return 0.0

    return round(
        travelers
        * days
        * max(0, cost_per_person_per_day),
        2,
    )


def calculate_accommodation_cost(
    travelers,
    nights,
    cost_per_person_per_night=None,
):
    try:
        travelers = max(1, int(travelers))
        nights = max(0, int(nights))
    except (TypeError, ValueError):
        return 0.0

    if cost_per_person_per_night is None:
        cost_per_person_per_night = DEFAULT_COSTS[
            "accommodation_per_person_per_day"
        ]

    try:
        cost_per_person_per_night = float(
            cost_per_person_per_night
        )
    except (TypeError, ValueError):
        return 0.0

    return round(
        travelers
        * nights
        * max(0, cost_per_person_per_night),
        2,
    )


def calculate_entry_fees(places, travelers=1):
    if not places:
        return 0.0

    try:
        travelers = max(1, int(travelers))
    except (TypeError, ValueError):
        travelers = 1

    total = 0.0

    for place in places:
        try:
            fee = float(
                place.get("entry_fee", 0)
            )
        except (TypeError, ValueError):
            fee = 0.0

        total += max(0, fee) * travelers

    return round(total, 2)


def calculate_miscellaneous_cost(
    days,
    cost_per_day=None,
):
    try:
        days = max(1, int(days))
    except (TypeError, ValueError):
        return 0.0

    if cost_per_day is None:
        cost_per_day = DEFAULT_COSTS[
            "miscellaneous_per_day"
        ]

    try:
        cost_per_day = float(cost_per_day)
    except (TypeError, ValueError):
        return 0.0

    return round(
        days * max(0, cost_per_day),
        2,
    )


def calculate_total_budget(
    distance_km,
    travelers,
    days,
    nights,
    places,
    transport_cost_per_km=None,
    food_cost_per_person_per_day=None,
    accommodation_cost_per_person_per_night=None,
    miscellaneous_cost_per_day=None,
    budget_level=None,
):
    transport_details = None
    if budget_level is not None:
        transport_details = calculate_cab_transport_cost(
            distance_km,
            days=days,
            budget_level=budget_level,
            travelers=travelers,
        )
        transport = transport_details["cost"]
    else:
        transport = calculate_transport_cost(
            distance_km,
            transport_cost_per_km,
        )

    food = calculate_food_cost(
        travelers,
        days,
        food_cost_per_person_per_day,
    )

    accommodation = calculate_accommodation_cost(
        travelers,
        nights,
        accommodation_cost_per_person_per_night,
    )

    entry_fees = calculate_entry_fees(
        places,
        travelers,
    )

    miscellaneous = calculate_miscellaneous_cost(
        days,
        miscellaneous_cost_per_day,
    )

    total = (
        transport
        + food
        + accommodation
        + entry_fees
        + miscellaneous
    )

    return {
        "transport": round(transport, 2),
        "transport_details": transport_details,
        "food": round(food, 2),
        "accommodation": round(
            accommodation,
            2,
        ),
        "entry_fees": round(
            entry_fees,
            2,
        ),
        "miscellaneous": round(
            miscellaneous,
            2,
        ),
        "total": round(total, 2),
    }