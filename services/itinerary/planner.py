"""Realistic day-by-day trip planning.

The planner turns a starting place and a set of destinations into days a
traveller could actually follow:

* Days stay geographically compact.
* Every new day preferably starts with a nearby temple.
* Temples are scheduled in the morning or after 4 pm.
* National parks, wildlife, zoos, dams, waterfalls, hills and other major
  outdoor activities are restricted to 09:00-18:00.
* Beaches are flexible, with evening preferred.
* Local parks are flexible, with morning/evening preferred.
* Malls and shopping areas are flexible within their opening hours.
* Driving time, lunch, visit duration and geographic compactness are included.
"""

from itertools import permutations

from services.nearby.distance import calculate_distance


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROAD_FACTOR = 1.3
AVERAGE_SPEED_KMH = 40
PARKING_MINUTES = 10

UNKNOWN_LEG_MINUTES = 30
MAX_LEG_MINUTES = 150
MAX_STOPS_PER_DAY = 6
DAY_SPAN_KM = 60

CANDIDATES_PER_STEP = 8
SEEDS_PER_DAY = 5

FIRST_LEG_MAX_MINUTES = 240
MAX_WAIT_MINUTES = 270

# If the first drive to a temple is long, prefer the evening temple session.
LONG_FIRST_LEG_TEMPLE_MINUTES = 90

LUNCH_FROM = 12 * 60 + 30
LUNCH_UNTIL = 14 * 60 + 30
LUNCH_MINUTES = 45

NOT_PREFERRED_PENALTY = 40


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _hm(text):
    hours, minutes = str(text).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def _clock(minutes):
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ---------------------------------------------------------------------------
# Opening-time profiles
# ---------------------------------------------------------------------------

# kind ->
# (
#     opening windows,
#     preferred windows,
#     default visit duration,
#     timing note
# )

_PROFILES = {
    "temple": (
        [
            ("05:30", "12:30"),
            ("16:00", "21:00"),
        ],
        [
            ("05:30", "11:00"),
            ("17:00", "20:30"),
        ],
        75,
        "Temples are usually closed from about 12:30 to 4 pm",
    ),

    # Major natural / external activities
    "wildlife": (
        [("09:00", "18:00")],
        [
            ("09:00", "11:30"),
            ("15:00", "18:00"),
        ],
        150,
        "Wildlife is easiest to see in the morning; parks close by 6 pm",
    ),

    "zoo": (
        [("09:00", "18:00")],
        [
            ("09:00", "12:00"),
            ("15:00", "18:00"),
        ],
        120,
        "Zoos are daytime attractions; visit between 9 am and 6 pm",
    ),

    "waterfall": (
        [("09:00", "18:00")],
        [
            ("09:00", "12:00"),
            ("15:00", "18:00"),
        ],
        90,
        "Outdoor spot - visit between 9 am and 6 pm",
    ),

    "nature": (
        [("09:00", "18:00")],
        [
            ("09:00", "12:00"),
            ("15:00", "18:00"),
        ],
        75,
        "Outdoor spot - visit between 9 am and 6 pm",
    ),

    "hill": (
        [("09:00", "18:00")],
        [
            ("09:00", "12:00"),
            ("15:00", "18:00"),
        ],
        120,
        "Outdoor spot - visit between 9 am and 6 pm",
    ),

    "adventure": (
        [("09:00", "18:00")],
        [
            ("09:00", "12:00"),
            ("15:00", "18:00"),
        ],
        180,
        "Outdoor activity - visit between 9 am and 6 pm",
    ),

    # Flexible activities
    "beach": (
        [("05:30", "21:00")],
        [("16:00", "20:30")],
        90,
        "Beach visits are flexible; evening is preferred",
    ),

    "park": (
        [("05:30", "21:00")],
        [
            ("06:00", "10:00"),
            ("16:00", "20:30"),
        ],
        60,
        "Local parks are flexible; morning or evening is preferred",
    ),

    "mall": (
        [("10:00", "22:00")],
        [
            ("10:00", "13:00"),
            ("16:00", "21:00"),
        ],
        120,
        "Malls are flexible and can be visited throughout their opening hours",
    ),

    "shopping": (
        [("10:00", "22:00")],
        [
            ("10:00", "13:00"),
            ("16:00", "21:00"),
        ],
        120,
        "Shopping areas are flexible and can be visited throughout their opening hours",
    ),

    # Heritage / historical
    "heritage": (
        [("09:00", "17:30")],
        [("10:00", "16:00")],
        75,
        "Museums and monuments keep daytime hours",
    ),

    "historical": (
        [("09:00", "17:30")],
        [("10:00", "16:00")],
        75,
        "Monuments keep daytime hours",
    ),

    "cultural": (
        [("06:00", "20:30")],
        [("08:00", "19:30")],
        45,
        "",
    ),
}


_DEFAULT_PROFILE = (
    [("08:00", "19:00")],
    [("09:00", "18:00")],
    60,
    "",
)


# ---------------------------------------------------------------------------
# Place classification
# ---------------------------------------------------------------------------

def place_profile(place):
    """Return opening windows, preferred windows, duration and timing note."""

    category = str(
        place.get("category_name")
        or place.get("category")
        or ""
    ).strip().casefold()

    name = str(
        place.get("place_name")
        or ""
    ).casefold()

    kind = category if category in _PROFILES else None

    # National parks / wildlife areas
    if any(
        word in name
        for word in (
            "national park",
            "wildlife sanctuary",
            "tiger reserve",
            "bird sanctuary",
            "wildlife reserve",
        )
    ):
        kind = "wildlife"

    # Zoo
    elif (
        "zoo" in name
        or "zoological" in name
    ):
        kind = "zoo"

    # Mall
    elif any(
        word in name
        for word in (
            "mall",
            "shopping centre",
            "shopping center",
        )
    ):
        kind = "mall"

    # IMPORTANT:
    # Local park remains flexible.
    # It must NOT be treated as a natural 09:00-18:00 activity.
    elif "park" in name:
        kind = "park"

    # Dams / reservoirs / waterfalls
    elif any(
        word in name
        for word in (
            "dam",
            "reservoir",
        )
    ):
        kind = "nature"

    elif any(
        word in name
        for word in (
            "waterfall",
            "falls",
        )
    ):
        kind = "waterfall"

    # Museum / heritage
    if any(
        word in name
        for word in (
            "museum",
            "gallery",
            "palace",
            "mahal",
        )
    ):
        kind = "heritage"

    windows, preferred, minutes, note = _PROFILES.get(
        kind,
        _DEFAULT_PROFILE,
    )

    try:
        stored = int(
            float(
                place.get("avg_visit_duration")
                or 0
            )
        )
    except (TypeError, ValueError):
        stored = 0

    duration = (
        stored
        if stored >= 20
        else minutes
    )

    return (
        [
            (_hm(a), _hm(b))
            for a, b in windows
        ],
        [
            (_hm(a), _hm(b))
            for a, b in preferred
        ],
        duration,
        note,
    )


def _kind(place):
    category = str(
        place.get("category_name")
        or place.get("category")
        or ""
    ).strip().casefold()

    name = str(
        place.get("place_name")
        or ""
    ).casefold()

    if any(
        word in name
        for word in (
            "national park",
            "wildlife sanctuary",
            "tiger reserve",
            "bird sanctuary",
        )
    ):
        return "wildlife"

    if "zoo" in name or "zoological" in name:
        return "zoo"

    if "park" in name:
        return "park"

    if any(
        word in name
        for word in (
            "dam",
            "reservoir",
        )
    ):
        return "nature"

    if any(
        word in name
        for word in (
            "waterfall",
            "falls",
        )
    ):
        return "waterfall"

    if any(
        word in name
        for word in (
            "museum",
            "gallery",
            "palace",
            "mahal",
        )
    ):
        return "museum"

    return category


def _is_temple(place):
    category = str(
        place.get("category_name")
        or place.get("category")
        or ""
    ).strip().casefold()

    name = str(
        place.get("place_name")
        or ""
    ).casefold()

    return (
        category == "temple"
        or "temple" in name
    )


# ---------------------------------------------------------------------------
# Timing notes
# ---------------------------------------------------------------------------

def timing_note(place, start_minute):
    """One friendly line on why this stop sits at this time of day."""

    kind = _kind(place)
    hour = start_minute / 60

    morning = hour < 12
    evening = hour >= 16

    if kind == "temple":
        if morning:
            return (
                "A morning darshan, before the temple closes "
                "for the afternoon."
            )

        if evening:
            return (
                "Timed for the evening, after the temple reopens "
                "at 4 pm - the evening pooja is worth staying for."
            )

        return (
            "Temple hours vary - many close around 12:30-4 pm, "
            "so check locally."
        )

    if kind == "wildlife":
        return (
            "Early hours are the best time to spot animals."
            if morning
            else
            "Parks close by 6 pm, so this visit wraps up before dusk."
        )

    if kind == "zoo":
        return (
            "Morning is a comfortable time for a zoo visit."
            if morning
            else
            "The zoo is kept within its daytime visiting window "
            "and wraps up by 6 pm."
        )

    if kind in (
        "waterfall",
        "nature",
        "hill",
        "adventure",
    ):
        return (
            "Cooler in the morning, and the light is lovely for photos."
            if morning
            else
            "A daylight visit - outdoor spots like this are best "
            "before 6 pm."
        )

    if kind in (
        "museum",
        "heritage",
        "historical",
    ):
        if 11 <= hour < 16:
            return (
                "Mostly indoors or shaded - a good way to spend "
                "the hottest part of the day."
            )

        return (
            "Monuments keep daytime hours, so this fits well here."
        )

    if kind == "beach":
        return (
            "The beach is at its best in the evening breeze."
            if evening
            else
            "Mornings here are calm and cool."
        )

    if kind == "park":
        return (
            "A pleasant evening for a relaxed local park visit."
            if evening
            else
            "A local park is flexible and works well in the cooler hours."
        )

    if kind in (
        "mall",
        "shopping",
    ):
        return (
            "A flexible indoor stop that can fit around "
            "the day's other visits."
        )

    return ""


# ---------------------------------------------------------------------------
# Coordinates / driving
# ---------------------------------------------------------------------------

def _coords(place):
    try:
        lat = float(place.get("latitude"))
        lon = float(place.get("longitude"))
    except (TypeError, ValueError):
        return None

    return lat, lon


def drive(a, b):
    """Return road distance and estimated driving minutes."""

    first = (
        a
        if isinstance(a, tuple)
        else (_coords(a) if a else None)
    )

    second = (
        b
        if isinstance(b, tuple)
        else (_coords(b) if b else None)
    )

    if not first or not second:
        return None, UNKNOWN_LEG_MINUTES

    km = (
        calculate_distance(
            first[0],
            first[1],
            second[0],
            second[1],
        )
        * ROAD_FACTOR
    )

    if km < 0.3:
        return round(km, 1), 0

    minutes = (
        km / AVERAGE_SPEED_KMH * 60
        + PARKING_MINUTES
    )

    return (
        round(km, 1),
        int(5 * round(minutes / 5)),
    )


# ---------------------------------------------------------------------------
# Route order
# ---------------------------------------------------------------------------

def route_order(places, start=None):
    """Destinations in driving order from start."""

    located = [
        p for p in places
        if _coords(p)
    ]

    unlocated = [
        p for p in places
        if not _coords(p)
    ]

    origin = (
        _coords(start)
        if start
        else None
    )

    order = []
    here = origin
    remaining = list(located)

    while remaining:

        if here is None:
            nxt = remaining[0]
        else:
            nxt = min(
                remaining,
                key=lambda p: calculate_distance(
                    here[0],
                    here[1],
                    *_coords(p),
                ),
            )

        remaining.remove(nxt)
        order.append(nxt)
        here = _coords(nxt)

    def leg(a, b):
        if not a or not b:
            return 0.0

        return calculate_distance(
            a[0],
            a[1],
            b[0],
            b[1],
        )

    # 2-opt
    points = [
        origin
    ] + [
        _coords(p)
        for p in order
    ]

    improved = True

    while improved and len(order) > 2:

        improved = False

        for i in range(
            1,
            len(points) - 2,
        ):

            for j in range(
                i + 1,
                len(points) - 1,
            ):

                current = (
                    leg(points[i - 1], points[i])
                    + leg(points[j], points[j + 1])
                )

                alternative = (
                    leg(points[i - 1], points[j])
                    + leg(points[i], points[j + 1])
                )

                if alternative + 1e-9 < current:

                    points[i:j + 1] = reversed(
                        points[i:j + 1]
                    )

                    order[i - 1:j] = reversed(
                        order[i - 1:j]
                    )

                    improved = True

    return order + unlocated


# ---------------------------------------------------------------------------
# One-day simulation
# ---------------------------------------------------------------------------

def _simulate(
    stops,
    origin,
    day_start,
    day_end,
    lunch=True,
):
    """Create a timeline for one day's stops."""

    now = day_start
    here = origin
    cost = 0.0
    entries = []
    lunched = not lunch

    for index, place in enumerate(stops):

        windows, preferred, minutes, _ = place_profile(
            place
        )

        # First stop can be the origin itself.
        if here is None and index == 0:
            km, travel = None, 0
        else:
            km, travel = drive(
                here,
                place,
            )

        # First leg may be longer because it moves to a new area.
        if travel > (
            FIRST_LEG_MAX_MINUTES
            if index == 0
            else MAX_LEG_MINUTES
        ):
            return None

        # ---------------------------------------------------------------
        # Lunch before moving to another attraction.
        # ---------------------------------------------------------------

        if (
            not lunched
            and LUNCH_FROM <= now < LUNCH_UNTIL
        ):
            entries.append(
                {
                    "kind": "lunch",
                    "start_minute": now,
                    "end_minute": now + LUNCH_MINUTES,
                }
            )

            now += LUNCH_MINUTES
            lunched = True

        arrive = now + travel

        # ---------------------------------------------------------------
        # Temple special rule.
        #
        # If the first drive of the day to a temple is long, do not
        # consume the remaining morning temple session. Wait for the
        # evening reopening instead.
        #
        # This fixes the long-drive case:
        #
        # 09:00 start
        #       ↓
        # long drive
        #       ↓
        # lunch
        #       ↓
        # 16:00 temple
        # ---------------------------------------------------------------

        force_temple_evening = (
            _is_temple(place)
            and index == 0
            and here is not None
            and travel >= LONG_FIRST_LEG_TEMPLE_MINUTES
            and arrive >= 10 * 60 + 30
        )

        slot = None

        for opens, closes in windows:

            # Skip the morning temple window when the long-drive rule
            # applies.
            if (
                force_temple_evening
                and opens < 16 * 60
            ):
                continue

            begin = max(
                arrive,
                opens,
            )

            if begin + minutes <= closes:
                slot = begin
                break

        if slot is None:
            return None

        if slot - arrive > MAX_WAIT_MINUTES:
            return None

        finish = slot + minutes

        if finish > day_end:
            return None

        wait = slot - arrive

        # ---------------------------------------------------------------
        # Lunch during waiting period.
        #
        # Example:
        # arrive at 10:35
        # temple opens at 16:00
        #
        # Lunch is inserted at 12:30 before the temple visit.
        # ---------------------------------------------------------------

        lunch_start = max(
            arrive,
            LUNCH_FROM,
        )

        lunch_during_wait = None

        if (
            not lunched
            and lunch_start < LUNCH_UNTIL
            and lunch_start + LUNCH_MINUTES <= slot
        ):
            lunch_during_wait = {
                "start_time": _clock(
                    lunch_start
                ),
                "end_time": _clock(
                    lunch_start + LUNCH_MINUTES
                ),
            }

            lunched = True
            wait -= LUNCH_MINUTES

        # ---------------------------------------------------------------
        # Preferred timing
        # ---------------------------------------------------------------

        in_preferred = any(
            begin <= slot
            and slot + minutes <= end
            for begin, end in preferred
        )

        cost += (
            travel
            + 0.6 * wait
            + (
                0
                if in_preferred
                else NOT_PREFERRED_PENALTY
            )
        )

        entries.append(
            {
                "kind": "visit",
                "place": place,
                "start_minute": slot,
                "end_minute": finish,
                "duration_minutes": minutes,
                "travel_km": km,
                "travel_minutes": travel,
                "wait_minutes": wait,
                "note": timing_note(
                    place,
                    slot,
                ),
                "preferred_slot": in_preferred,
                "lunch_before": lunch_during_wait,
            }
        )

        now = finish

        destination = _coords(place)

        if destination:
            here = destination

    return entries, cost


# ---------------------------------------------------------------------------
# Best order for one day
# ---------------------------------------------------------------------------

def _best_day(
    stops,
    origin,
    day_start,
    day_end,
    fixed_first=None,
):
    """Find the cheapest feasible visiting order."""

    free = [
        p
        for p in stops
        if p is not fixed_first
    ]

    best = None

    if len(free) <= 7:
        candidates = permutations(free)
    else:
        candidates = [tuple(free)]

    for order in candidates:

        sequence = (
            [fixed_first]
            if fixed_first is not None
            else []
        ) + list(order)

        result = _simulate(
            sequence,
            origin,
            day_start,
            day_end,
        )

        if result and (
            best is None
            or result[1] < best[1]
        ):
            best = result

    return best


# ---------------------------------------------------------------------------
# Temple helpers
# ---------------------------------------------------------------------------

def _nearby_temple(places, origin):
    """Return the nearest unused temple to the previous day's location."""

    temples = [
        p
        for p in places
        if _is_temple(p)
    ]

    if not temples:
        return None

    if not origin:
        return temples[0]

    return min(
        temples,
        key=lambda p: _nearest_km(
            p,
            [origin],
        ),
    )


# ---------------------------------------------------------------------------
# Main itinerary planner
# ---------------------------------------------------------------------------

def plan_trip(
    places,
    start_place=None,
    days=1,
    start_time="09:00",
    end_time="18:00",
):
    """Plan a multi-day trip.

    Day 1:
        * Preserve the user's selected starting place.
        * If it is a temple, it remains the first stop.

    Day 2+:
        * Start with the nearest unused temple to the previous day's
          final location.

    Timing:
        * Natural/external activities: 09:00-18:00.
        * Beaches: flexible, evening preferred.
        * Local parks: flexible.
        * Malls/shopping: flexible within opening hours.
    """

    try:
        days = max(
            1,
            int(days),
        )
    except (TypeError, ValueError):
        days = 1

    day_start = _hm(start_time)
    day_end = _hm(end_time)

    if day_end <= day_start:
        day_end = day_start + 8 * 60

    start_id = (
        start_place or {}
    ).get("place_id")

    seen = set()
    unique = []

    for place in places or []:

        key = (
            place.get("place_id")
            or place.get("place_name")
        )

        if key in seen:
            continue

        if (
            start_id is not None
            and place.get("place_id") == start_id
        ):
            continue

        seen.add(key)
        unique.append(dict(place))

    # Places that cannot fit the day are reported as unscheduled.
    unscheduled = [
        p
        for p in unique
        if _best_day(
            [p],
            _coords(p),
            day_start,
            day_end,
        ) is None
    ]

    remaining = [
        p
        for p in route_order(
            unique,
            start_place,
        )
        if p not in unscheduled
    ]

    origin = (
        _coords(start_place)
        if start_place
        else None
    )

    plan_days = []

    # ---------------------------------------------------------------
    # Build each day
    # ---------------------------------------------------------------

    for day_number in range(
        1,
        days + 1,
    ):

        fixed = None

        # -----------------------------------------------------------
        # Day 1:
        # preserve selected starting place.
        # -----------------------------------------------------------

        if (
            day_number == 1
            and start_place
        ):
            fixed = dict(
                start_place,
                is_start=True,
            )

        # -----------------------------------------------------------
        # Day 2 onward:
        # nearest available temple.
        # -----------------------------------------------------------

        else:

            temple_anchor = _nearby_temple(
                remaining,
                origin,
            )

            if temple_anchor:

                fixed = dict(
                    temple_anchor,
                    is_start=True,
                )

                remaining.remove(
                    temple_anchor
                )

        chosen = (
            [fixed]
            if fixed
            else []
        )

        best = (
            _best_day(
                chosen,
                origin,
                day_start,
                day_end,
                fixed_first=fixed,
            )
            if fixed
            else None
        )

        # If fixed starting place cannot fit its normal hours,
        # preserve it as the starting stop.
        if fixed and best is None:

            minutes = place_profile(
                fixed
            )[2]

            best = (
                [
                    {
                        "kind": "visit",
                        "place": fixed,
                        "start_minute": day_start,
                        "end_minute": day_start + minutes,
                        "duration_minutes": minutes,
                        "travel_km": None,
                        "travel_minutes": 0,
                        "wait_minutes": 0,
                        "note": timing_note(
                            fixed,
                            day_start,
                        ),
                        "preferred_slot": False,
                    }
                ],
                0,
            )

        # -----------------------------------------------------------
        # Grow the day around the fixed starting point.
        # -----------------------------------------------------------

        if fixed:

            chosen, grown = _grow_day(
                chosen,
                remaining,
                origin,
                day_start,
                day_end,
                fixed,
            )

            best = grown or best

        else:

            # Try several nearby seeds.
            anchors = (
                [origin]
                if origin
                else []
            )

            seeds = sorted(
                remaining,
                key=lambda p: _nearest_km(
                    p,
                    anchors,
                ),
            )[:SEEDS_PER_DAY]

            options = []

            for seed in seeds:

                if (
                    _best_day(
                        [seed],
                        origin,
                        day_start,
                        day_end,
                    )
                    is None
                ):
                    continue

                day_stops, grown = _grow_day(
                    [seed],
                    [
                        p
                        for p in remaining
                        if p is not seed
                    ],
                    origin,
                    day_start,
                    day_end,
                    None,
                )

                if grown:

                    drive_minutes = sum(
                        e.get("travel_minutes") or 0
                        for e in grown[0]
                        if e["kind"] == "visit"
                    )

                    options.append(
                        (
                            -len(day_stops),
                            drive_minutes,
                            day_stops,
                            grown,
                        )
                    )

            if options:

                _, _, chosen, best = min(
                    options,
                    key=lambda item: (
                        item[0],
                        item[1],
                    ),
                )

            for place in chosen:

                if place in remaining:
                    remaining.remove(place)

        if best is None:
            continue

        # -----------------------------------------------------------
        # Finalize entries.
        # -----------------------------------------------------------

        entries = best[0]

        for entry in entries:

            entry["start_time"] = _clock(
                entry["start_minute"]
            )

            entry["end_time"] = _clock(
                entry["end_minute"]
            )

            if entry["kind"] == "visit":
                entry["is_start"] = bool(
                    entry["place"].get("is_start")
                )

        visits = [
            e
            for e in entries
            if e["kind"] == "visit"
        ]

        plan_days.append(
            {
                "day": len(plan_days) + 1,
                "entries": entries,
                "drive_km": round(
                    sum(
                        e["travel_km"] or 0
                        for e in visits
                    ),
                    1,
                ),
                "drive_minutes": sum(
                    e["travel_minutes"] or 0
                    for e in visits
                ),
            }
        )

        # The next day begins near the final location of this day.
        last = next(
            (
                _coords(e["place"])
                for e in reversed(visits)
                if _coords(e["place"])
            ),
            None,
        )

        origin = last or origin

        if not remaining:
            break

    unscheduled += remaining

    return {
        "days": plan_days,
        "unscheduled": unscheduled,
        "total_km": round(
            sum(
                day["drive_km"]
                for day in plan_days
            ),
            1,
        ),
    }


# ---------------------------------------------------------------------------
# Grow a day
# ---------------------------------------------------------------------------

def _grow_day(
    chosen,
    remaining,
    origin,
    day_start,
    day_end,
    fixed,
):
    """Add nearby stops that still fit the day."""

    chosen = list(chosen)

    best = _best_day(
        chosen,
        origin,
        day_start,
        day_end,
        fixed_first=fixed,
    )

    while (
        remaining
        and len(chosen)
        < MAX_STOPS_PER_DAY
        + (1 if fixed else 0)
    ):

        anchors = [
            c
            for c in (
                _coords(p)
                for p in chosen
            )
            if c
        ]

        if not anchors and origin:
            anchors = [origin]

        options = sorted(
            (
                p
                for p in remaining
                if _fits_span(
                    p,
                    chosen,
                )
            ),
            key=lambda p: _nearest_km(
                p,
                anchors,
            ),
        )

        for candidate in options[
            :CANDIDATES_PER_STEP
        ]:

            attempt = _best_day(
                chosen + [candidate],
                origin,
                day_start,
                day_end,
                fixed_first=fixed,
            )

            if attempt:

                chosen.append(candidate)
                remaining.remove(candidate)

                best = attempt
                break

        else:
            break

    return chosen, best


# ---------------------------------------------------------------------------
# Distance helpers
# ---------------------------------------------------------------------------

def _nearest_km(place, anchors):
    """Distance from place to the closest anchor."""

    here = _coords(place)

    if not here or not anchors:
        return 10_000.0

    return min(
        calculate_distance(
            here[0],
            here[1],
            anchor[0],
            anchor[1],
        )
        for anchor in anchors
    )


def _fits_span(place, chosen):
    """Keep destinations geographically compact."""

    here = _coords(place)

    if not here:
        return True

    return all(
        calculate_distance(
            here[0],
            here[1],
            *coords,
        ) <= DAY_SPAN_KM
        for coords in (
            _coords(p)
            for p in chosen
        )
        if coords
    )