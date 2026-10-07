import random

import streamlit as st
from geopy.geocoders import Nominatim

from database.queries import get_all_places, get_districts
from services.nearby.distance import calculate_distance
from services.recommendation.scoring import calculate_recommendation_score
from services.recommendation.interest_matching import match_user_interests
from services.recommendation.rating_confidence import (
    add_rating_confidence_to_places,
)
from services.recommendation.popularity import add_popularity_to_places
from services.status.place_status import add_status_to_places
from ui.components.page_hero import render_page_hero
from ui.components.ranked_list import render_ranked_list


INTERESTS = [
    "Temple",
    "Beach",
    "Hill",
    "Waterfall",
    "Wildlife",
    "Heritage",
    "Nature",
    "Historical",
    "Cultural",
    "Adventure",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique(values):
    return sorted(
        {
            str(v).strip()
            for v in values
            if v and str(v).strip()
        }
    )


def _place_label(place):
    """
    Display place name and city/town.
    """
    place_name = str(
        place.get("place_name")
        or "Unknown Place"
    ).strip()

    city = str(
        place.get("city_town")
        or place.get("city")
        or ""
    ).strip()

    if city and city.casefold() != place_name.casefold():
        return f"{place_name} - {city}"

    return place_name


def _place_map(places):
    return {
        int(p["place_id"]): p
        for p in places
        if p.get("place_id") is not None
    }


def _place_select(label, places, key):
    """
    Searchable starting-place selector.
    """
    lookup = _place_map(places)

    if not lookup:
        return None

    selected_id = st.selectbox(
        label,
        list(lookup),
        key=key,
        format_func=lambda place_id: _place_label(
            lookup[place_id]
        ),
    )

    return lookup.get(selected_id)


# ---------------------------------------------------------------------------
# Coordinate handling
# ---------------------------------------------------------------------------

def _resolve_coordinates(place):
    """
    Resolve missing coordinates for a selected starting place.

    Resolved coordinates are kept in session state only.
    """

    if not place:
        return place

    try:
        lat = float(
            place.get("latitude")
        )
        lon = float(
            place.get("longitude")
        )

        if (
            -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            return place

    except (
        TypeError,
        ValueError,
    ):
        pass

    cache = st.session_state.setdefault(
        "recommendation_geocode_cache",
        {},
    )

    cache_key = "|".join(
        str(
            place.get(key)
            or ""
        ).strip()
        for key in (
            "place_name",
            "city_town",
            "district",
        )
    )

    if cache_key in cache:

        result = dict(place)

        result.update(
            cache[cache_key]
        )

        return result

    query_parts = [
        place.get("place_name"),
        place.get("city_town"),
        place.get("district"),
        "Tamil Nadu",
        "India",
    ]

    query = ", ".join(
        str(x).strip()
        for x in query_parts
        if x and str(x).strip()
    )

    try:

        geocoder = Nominatim(
            user_agent=(
                "smart-tamilnadu-tourism-"
                "recommendations"
            )
        )

        location = geocoder.geocode(
            query,
            timeout=5,
        )

    except Exception:

        location = None

    if location is None:

        cache[cache_key] = {}

        return place

    coords = {
        "latitude": float(
            location.latitude
        ),
        "longitude": float(
            location.longitude
        ),
    }

    cache[cache_key] = coords

    result = dict(place)

    result.update(coords)

    return result


# ---------------------------------------------------------------------------
# Nearby places
# ---------------------------------------------------------------------------

def _nearby_places(
    reference,
    places,
    radius_km,
):
    """
    Find places within the selected travel distance.
    """

    if not reference:
        return []

    reference = _resolve_coordinates(
        reference
    )

    if (
        reference.get("latitude") is None
        or reference.get("longitude") is None
    ):
        return []

    result = []

    for place in places:

        # Do not recommend the starting place itself.
        if (
            place.get("place_id")
            == reference.get("place_id")
        ):
            continue

        try:

            place_lat = place.get(
                "latitude"
            )

            place_lon = place.get(
                "longitude"
            )

            if (
                place_lat is None
                or place_lon is None
            ):
                continue

            distance = calculate_distance(
                reference.get("latitude"),
                reference.get("longitude"),
                place_lat,
                place_lon,
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            distance is not None
            and distance <= radius_km
        ):

            item = dict(place)

            item["distance_km"] = distance

            result.append(item)

    result.sort(
        key=lambda p: (
            float(
                p.get(
                    "distance_km",
                    9999,
                )
            ),
            -float(
                p.get(
                    "rating",
                    0,
                )
                or 0
            ),
        )
    )

    return result


# ---------------------------------------------------------------------------
# Interest filtering
# ---------------------------------------------------------------------------

def _filter_interests(
    places,
    interests,
):
    """
    Filter places according to selected interests.

    If no interests are selected, all nearby places remain eligible.
    """

    if not interests:
        return places

    wanted = {
        x.casefold()
        for x in interests
    }

    return [
        p
        for p in places
        if (
            any(
                x in str(
                    p.get(
                        "category_name",
                        "",
                    )
                ).casefold()
                for x in wanted
            )
            or
            any(
                x in str(
                    p.get(
                        "subcategory",
                        "",
                    )
                ).casefold()
                for x in wanted
            )
        )
    ]


# ---------------------------------------------------------------------------
# Recommendation ranking
# ---------------------------------------------------------------------------

def _rank(
    places,
    interests,
):
    """
    Apply the existing recommendation pipeline.
    """

    places = add_status_to_places(
        add_rating_confidence_to_places(
            add_popularity_to_places(
                places
            )
        )
    )

    matched_places = match_user_interests(
        places,
        interests,
    )

    scored_places = []

    for place in matched_places:

        place_data = dict(place)

        try:

            score = calculate_recommendation_score(
                place_data
            )

        except Exception:

            score = float(
                place_data.get(
                    "rating",
                    0,
                )
                or 0
            )

        place_data[
            "recommendation_score"
        ] = score

        scored_places.append(
            place_data
        )

    # Keep a stable random tie-breaker
    # during the current session.
    session_seed = st.session_state.setdefault(
        "recommendation_shuffle_seed",
        random.randint(
            0,
            1_000_000,
        ),
    )

    tie_breaker = random.Random(
        session_seed
    )

    tie_values = {
        item.get("place_id"):
            tie_breaker.random()
        for item in scored_places
    }

    scored_places.sort(
        key=lambda item: (
            item.get(
                "recommendation_score",
                0,
            ),
            -float(
                item.get(
                    "distance_km",
                    0,
                )
                or 0
            ),
            tie_values.get(
                item.get("place_id"),
                0,
            ),
        ),
        reverse=True,
    )

    return scored_places


# ---------------------------------------------------------------------------
# Recommendations page
# ---------------------------------------------------------------------------

def render_recommendations_page():

    # -----------------------------------------------------------------------
    # Page hero
    # -----------------------------------------------------------------------

    render_page_hero(
        "Curated for you",
        "Recommended for you",
        (
            "Tell us where you are and what you enjoy; "
            "we rank the places worth the trip."
        ),
        photo_categories=[
            "Hill",
            "Waterfall",
            "Wildlife",
        ],
    )

    # -----------------------------------------------------------------------
    # Load places
    # -----------------------------------------------------------------------

    places = [
        dict(place)
        for place in get_all_places()
    ]

    if not places:

        st.info(
            "No destinations are available "
            "for recommendations."
        )

        return

    # -----------------------------------------------------------------------
    # Recommendation form
    # -----------------------------------------------------------------------

    with st.container(
        key="planner_panel_recommendations"
    ):

        st.markdown(
            '<div class="panel-title">'
            "Find places for you"
            "</div>",
            unsafe_allow_html=True,
        )

        # ---------------------------------------------------------------
        # Interests
        # ---------------------------------------------------------------

        interests = st.multiselect(
            "What are you interested in?",
            INTERESTS,
            key="recommendation_interests",
            placeholder="Choose places you like",
        )

        # ---------------------------------------------------------------
        # Starting Place + District
        # ---------------------------------------------------------------

        col_start, col_district = st.columns(
            [1.35, 1]
        )

        # Select the district first so the Start Place dropdown can be
        # shortlisted to that district without changing the page layout.
        with col_district:

            districts = _unique(
                [
                    row["district"]
                    for row in get_districts()
                ]
            )

            district_options = [
                "All Districts"
            ] + districts

            district = st.selectbox(
                "District (Optional)",
                district_options,
                key="recommendation_plan_district",
            )

        with col_start:

            if district != "All Districts":
                start_place_options = [
                    place
                    for place in places
                    if str(place.get("district") or "").strip().casefold()
                    == str(district).strip().casefold()
                ]
            else:
                start_place_options = places

            # Clear a stale Start Place when the selected district changes.
            valid_start_ids = {
                place.get("place_id")
                for place in start_place_options
            }
            previous_start = st.session_state.get(
                "recommendation_plan_start"
            )
            if previous_start is not None and previous_start not in valid_start_ids:
                st.session_state.pop(
                    "recommendation_plan_start",
                    None,
                )

            starting_place = _place_select(
                "Enter your starting place",
                start_place_options,
                "recommendation_plan_start",
            )

        # ---------------------------------------------------------------
        # Travel distance
        # ---------------------------------------------------------------

        radius = st.selectbox(
            "How far do you want to travel?",
            [10, 25, 50, 75, 100],
            index=2,
            format_func=lambda x: f"{x} km",
            key="recommendation_plan_radius",
        )

        # ---------------------------------------------------------------
        # PROCESSING BUTTON
        #
        # IMPORTANT:
        # This uses the EXACT existing project button approach used
        # by Itinerary:
        #
        #     type="primary"
        #     use_container_width=True
        #
        # The existing CSS automatically gives it:
        # - teal gradient
        # - rounded/pill shape
        # - no border
        # - existing shadow
        #
        # No new CSS is added here.
        # ---------------------------------------------------------------

        if st.button(
            "🔍 Find Recommendations",
            type="primary",
            use_container_width=True,
            key="find_recommendations_button",
        ):

            # -----------------------------------------------------------
            # Validate starting place
            # -----------------------------------------------------------

            if not starting_place:

                st.warning(
                    "Please select your starting place "
                    "before finding recommendations."
                )

                return

            # -----------------------------------------------------------
            # Process recommendations
            # -----------------------------------------------------------

            with st.spinner(
                "Finding the best places for you..."
            ):

                # -------------------------------------------------------
                # Step 1:
                # Find nearby places
                # -------------------------------------------------------

                candidates = _nearby_places(
                    starting_place,
                    places,
                    radius,
                )

                # -------------------------------------------------------
                # Step 2:
                # HARD DISTANCE SAFETY GATE
                #
                # No place outside the selected radius can ever
                # reach the recommendation ranking stage.
                # -------------------------------------------------------

                candidates = [
                    item
                    for item in candidates
                    if (
                        item.get(
                            "distance_km"
                        ) is not None
                        and float(
                            item[
                                "distance_km"
                            ]
                        )
                        <= float(radius)
                        + 1e-9
                    )
                ]

                # -------------------------------------------------------
                # Step 3:
                # Optional district filter
                # -------------------------------------------------------

                if district != "All Districts":

                    candidates = [
                        item
                        for item in candidates
                        if str(
                            item.get(
                                "district",
                                "",
                            )
                        ).casefold()
                        == str(
                            district
                        ).casefold()
                    ]

                # -------------------------------------------------------
                # Step 4:
                # Interest filter
                # -------------------------------------------------------

                candidates = _filter_interests(
                    candidates,
                    interests,
                )

                # -------------------------------------------------------
                # Step 5:
                # Rank recommendations
                # -------------------------------------------------------

                ranked = _rank(
                    candidates,
                    interests,
                )

                # -------------------------------------------------------
                # Step 6:
                # Show top 10 recommendations
                # -------------------------------------------------------

                recommended_places = ranked[:10]

            # -----------------------------------------------------------
            # Results
            # -----------------------------------------------------------

            if district != "All Districts":

                st.caption(
                    f"Showing places within "
                    f"{radius} km of "
                    f"{_place_label(starting_place)} "
                    f"in {district}."
                )

            else:

                st.caption(
                    f"Showing places within "
                    f"{radius} km of "
                    f"{_place_label(starting_place)}."
                )

            st.markdown(
                '<div class="section-title">'
                "Top Recommendations"
                "</div>",
                unsafe_allow_html=True,
            )

            if not recommended_places:

                if interests:

                    st.info(
                        "No recommendations match "
                        "your selected interests within "
                        "the selected travel distance. "
                        "Try increasing the travel distance "
                        "or choosing fewer interests."
                    )

                else:

                    st.info(
                        "No tourist destinations were found "
                        "within the selected travel distance."
                    )

                return

            # -----------------------------------------------------------
            # Existing recommendation cards
            # -----------------------------------------------------------

            render_ranked_list(
                recommended_places
            )


if __name__ == "__main__":
    render_recommendations_page()