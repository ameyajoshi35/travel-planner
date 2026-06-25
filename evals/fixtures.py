"""
Eval fixtures — sample TripContexts and pre-baked plan/transport/hotel
outputs that the offline tests run against without making any API calls.
"""

from travel_planner.models import TripContext

# ── Sample trip inputs (the "eval dataset") ───────────────────────────────────

TRIPS = {
    "rajasthan_couple": TripContext(
        destination="Jaipur, Rajasthan",
        state="Rajasthan",
        starting_city="Mumbai",
        travel_month="October",
        duration_days=5,
        num_travelers=2,
        budget_total=40_000,
        traveler_type="couple",
        experience_type=["heritage", "nature"],
        is_confirmed=True,
    ),
    "kerala_family": TripContext(
        state="Kerala",
        starting_city="Delhi",
        travel_month="December",
        duration_days=7,
        num_travelers=4,
        budget_total=80_000,
        traveler_type="family",
        has_kids=True,
        experience_type=["beach", "nature"],
        is_confirmed=True,
    ),
    "himachal_friends": TripContext(
        destination="Manali, Himachal Pradesh",
        state="Himachal Pradesh",
        starting_city="Delhi",
        travel_month="June",
        duration_days=6,
        num_travelers=4,
        budget_total=60_000,
        traveler_type="friends",
        experience_type=["adventure", "nature"],
        is_confirmed=True,
    ),
}

# ── Pre-baked plan fixtures (used for fast offline tests) ─────────────────────
# These mirror what synthesize_json() would return for the trips above.

PLANS = {
    "good_plan": {
        "trip_title": "Rajasthan Heritage Trail",
        "overview": (
            "Explore the royal palaces and ancient forts of Rajasthan, "
            "soaking in the golden hues of the Thar Desert and vibrant bazaars. "
            "A perfect romantic getaway from Mumbai to the Pink City."
        ),
        "destinations": [
            {
                "name": "Jaipur",
                "tagline": "The Pink City of Royals",
                "description": "Home to magnificent forts and palaces.",
                "history": "Founded in 1727 by Maharaja Sawai Jai Singh II.",
                "unique_facts": ["Only planned city of its era", "Pink walls by royal decree"],
                "fun_activities": ["Elephant ride at Amer Fort", "Bazaar walk"],
                "highlights": ["Amer Fort", "Hawa Mahal", "City Palace"],
            }
        ],
        "itinerary": [
            {
                "day": 1, "title": "Arrival in Jaipur",
                "location": "Jaipur",
                "fun_highlight": "First view of the illuminated Hawa Mahal at dusk",
                "morning": "Fly Mumbai → Jaipur, check in",
                "afternoon": "City Palace tour",
                "evening": "Dinner at Chokhi Dhani",
                "stay": "Jaipur",
            },
            {
                "day": 2, "title": "Forts and Bazaars",
                "location": "Jaipur",
                "fun_highlight": "Sunrise at Amer Fort",
                "morning": "Amer Fort elephant ride",
                "afternoon": "Jaigarh Fort",
                "evening": "Johari Bazaar shopping",
                "stay": "Jaipur",
            },
            {
                "day": 3, "title": "Day trip to Ranthambore",
                "location": "Ranthambore",
                "fun_highlight": "Tiger sighting on safari",
                "morning": "Drive to Ranthambore",
                "afternoon": "Jungle safari",
                "evening": "Return to Jaipur",
                "stay": "Jaipur",
            },
            {
                "day": 4, "title": "Stepwells and Sunset",
                "location": "Jaipur",
                "fun_highlight": "Sunset at Nahargarh Fort",
                "morning": "Chand Baori stepwell",
                "afternoon": "Nahargarh Fort",
                "evening": "Rooftop dinner",
                "stay": "Jaipur",
            },
            {
                "day": 5, "title": "Departure",
                "location": "Jaipur",
                "fun_highlight": "Last chai at a local dhaba",
                "morning": "Local market visit",
                "afternoon": "Depart Jaipur",
                "evening": "Home",
                "stay": "",
            },
        ],
        "budget": {
            "transport": 12_000,
            "accommodation": 15_000,
            "food": 7_000,
            "activities": 5_000,
        },
        "tips": [
            "Book Amer Fort tickets online to avoid queues.",
            "October is ideal — cooler and post-monsoon green.",
            "Bargain at Johari Bazaar for textiles.",
            "Carry cash — many small shops don't accept cards.",
        ],
    },

    "bad_plan_missing_sections": {
        # Missing itinerary and budget — should fail completeness eval
        "trip_title": "Quick Rajasthan Trip",
        "overview": "A trip to Rajasthan.",
        "destinations": [{"name": "Jaipur", "tagline": "Pink City"}],
        "tips": ["Pack sunscreen"],
    },

    "bad_plan_wrong_duration": {
        # Only 2 days for a 5-day trip — should fail duration eval
        "trip_title": "Rajasthan Short Trip",
        "overview": "A short Rajasthan trip.",
        "destinations": [{"name": "Jaipur", "tagline": "Pink City", "description": "Heritage city"}],
        "itinerary": [
            {"day": 1, "title": "Arrival", "location": "Jaipur",
             "fun_highlight": "City Palace", "morning": "Arrive", "afternoon": "City Palace",
             "evening": "Dinner", "stay": "Jaipur"},
            {"day": 2, "title": "Departure", "location": "Jaipur",
             "fun_highlight": "Markets", "morning": "Markets", "afternoon": "Depart",
             "evening": "Home", "stay": ""},
        ],
        "budget": {"transport": 10_000, "accommodation": 8_000, "food": 5_000, "activities": 2_000},
        "tips": ["Book early"],
    },

    "bad_plan_over_budget": {
        # Budget ₹80,000 on a ₹40,000 trip — should fail budget eval
        "trip_title": "Luxury Rajasthan",
        "overview": "Lavish Rajasthan heritage tour.",
        "destinations": [{"name": "Jaipur", "tagline": "Pink City", "description": "Heritage city"}],
        "itinerary": [
            {"day": i + 1, "title": f"Day {i+1}", "location": "Jaipur",
             "fun_highlight": "Exploring", "morning": "Sightseeing", "afternoon": "More sights",
             "evening": "Fine dining", "stay": "Jaipur"}
            for i in range(5)
        ],
        "budget": {"transport": 20_000, "accommodation": 35_000, "food": 15_000, "activities": 10_000},
        "tips": ["Splurge on the heritage hotels"],
    },

    "bad_plan_wrong_state": {
        # Destinations in Goa instead of Rajasthan — should fail scope eval
        "trip_title": "Beach Getaway",
        "overview": "Sun and sand on Goa's pristine beaches.",
        "destinations": [{"name": "Goa", "tagline": "Beach Paradise", "description": "Beautiful beaches"}],
        "itinerary": [
            {"day": i + 1, "title": f"Day {i+1}", "location": "Goa",
             "fun_highlight": "Beach day", "morning": "Beach", "afternoon": "Water sports",
             "evening": "Sunset cruise", "stay": "Goa"}
            for i in range(5)
        ],
        "budget": {"transport": 10_000, "accommodation": 15_000, "food": 8_000, "activities": 7_000},
        "tips": ["Rent a scooter"],
    },
}

TRANSPORT_FIXTURE = {
    "options": [
        {
            "airlines": "IndiGo",
            "route": "Mumbai → Jaipur",
            "duration": "1h 55min",
            "cost_per_person": "₹4,200",
            "class": "Economy",
            "booking_tip": "Book 3 weeks ahead on MakeMyTrip",
        }
    ],
    "sources": [{"title": "IndiGo fares", "url": "https://www.goindigo.in"}],
}

HOTELS_FIXTURE = {
    "Jaipur": [
        {
            "name": "Hotel Pearl Palace",
            "type": "Budget",
            "price_per_night": "₹1,800",
            "rating": "4.3/5",
            "why_pick": "Best value near old city",
        },
        {
            "name": "Samode Haveli",
            "type": "Mid-range",
            "price_per_night": "₹5,500",
            "rating": "4.6/5",
            "why_pick": "Authentic heritage haveli experience",
        },
        {
            "name": "Rambagh Palace",
            "type": "Luxury",
            "price_per_night": "₹22,000",
            "rating": "4.9/5",
            "why_pick": "Former royal residence, iconic Jaipur landmark",
        },
    ]
}
