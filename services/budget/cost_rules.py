COST_RULES = {
    # Indicative Coimbatore cab/day-package assumptions. These are
    # estimates, not live booking prices. The calculator also applies
    # included kilometres and driver allowance instead of pretending that
    # every cab charges a flat per-km rate.
    "transport": {
        "budget": 11.0,
        "standard": 12.0,
        "premium": 17.0,
    },
    "transport_package": {
        "budget": {
            "vehicle": "Sedan",
            "capacity": 4,
            "base_per_day": 2250.0,
            "included_km_per_day": 100.0,
            "extra_km_rate": 11.0,
            "driver_allowance_per_day": 350.0,
        },
        "standard": {
            "vehicle": "Sedan",
            "capacity": 4,
            "base_per_day": 2700.0,
            "included_km_per_day": 100.0,
            "extra_km_rate": 12.0,
            "driver_allowance_per_day": 400.0,
        },
        "premium": {
            "vehicle": "Innova Crysta",
            "capacity": 7,
            "base_per_day": 4800.0,
            "included_km_per_day": 100.0,
            "extra_km_rate": 17.0,
            "driver_allowance_per_day": 400.0,
        },
    },
    "food_per_person_per_day": {
        "budget": 300.0,
        "standard": 500.0,
        "premium": 900.0,
    },
    "accommodation_per_person_per_night": {
        "budget": 700.0,
        "standard": 1200.0,
        "premium": 2500.0,
    },
    "miscellaneous_per_day": {
        "budget": 100.0,
        "standard": 200.0,
        "premium": 400.0,
    },
}


BUDGET_LEVELS = [
    "budget",
    "standard",
    "premium",
]


def get_cost_rule(category, budget_level="standard"):
    if category not in COST_RULES:
        return 0.0

    if budget_level not in BUDGET_LEVELS:
        budget_level = "standard"

    return COST_RULES[category].get(
        budget_level,
        0.0,
    )


def get_budget_rules(budget_level="standard"):
    if budget_level not in BUDGET_LEVELS:
        budget_level = "standard"

    return {
        category: values.get(
            budget_level,
            0.0,
        )
        for category, values in COST_RULES.items()
    }


def calculate_estimated_daily_cost(
    budget_level="standard",
):
    rules = get_budget_rules(budget_level)

    return round(
        rules["food_per_person_per_day"]
        + rules["accommodation_per_person_per_night"]
        + rules["miscellaneous_per_day"],
        2,
    )