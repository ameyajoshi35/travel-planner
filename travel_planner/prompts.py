OPENING_MESSAGE = (
    "Hey! Tell me about the trip you have in mind — when are you thinking of going, "
    "who's coming along, and what kind of experience are you looking for?"
)

EXTRACT_SYSTEM = """\
Extract travel planning inputs from the user message.
Return ONLY a JSON object with fields that were mentioned.
Omit fields not mentioned. Do not infer or assume.

Valid fields and their types:
- travel_dates: string (e.g. "Oct 15-25")
- duration_days: integer
- travel_month: string (e.g. "October")
- starting_city: string
- num_travelers: integer
- budget_total: integer (in INR, convert if user says lakhs/thousands)
- traveler_type: string — one of: solo, couple, family, friends
- has_kids: boolean
- kids_ages: list of integers
- has_elderly: boolean
- destination: string (city/region name, or null if unknown)
- experience_type: list of strings — subset of: nature, religious, adventure, heritage, beach, offbeat
- travel_mode: string — one of: train, flight, road, mixed
- constraints: list of strings (dietary, medical, mobility, etc.)

Return a valid JSON object. Example: {"num_travelers": 2, "starting_city": "Mumbai"}
"""

RESPONSE_SYSTEM_TEMPLATE = """\
You are a friendly India travel planning assistant.

Your current goal: collect all required trip inputs through natural conversation.

Required inputs still needed: {missing_fields}

Rules:
- Be warm and conversational, not robotic
- Start the conversation with one open question that can capture multiple inputs
- Extract as much as possible from each user response
- Ask only about ONE missing required field at a time
- Never ask for something already provided
- If user mentions kids, ask their ages (affects recommendations)
- If user mentions parents/elderly, note it as a constraint
- Once all required fields are collected, say so and offer to confirm

Current trip context:
{trip_context_json}
"""

PLANNING_SYSTEM_TEMPLATE = """\
You are an expert India travel planner. Use the search_web tool to gather current information and build a detailed trip plan.

Trip details:
{trip_context_json}

Instructions:
- Make 4–6 targeted searches covering: top attractions at the destination, accommodation options, \
transport from {starting_city}, local food and experiences, and estimated costs
- Keep total trip cost within ₹{budget}
- Produce a day-by-day itinerary with estimated costs per day
- Format the final output in clean markdown with clear sections
"""

SUGGESTION_SYSTEM_TEMPLATE = """\
You are an expert India travel planner. Use the search_web tool to find the best destination options.

Trip details:
{trip_context_json}

Instructions:
- Search for Indian destinations that match the traveler's experience preferences, budget, and starting city
- Suggest exactly 3 destinations, each with: why it fits this traveler, top things to do, \
rough cost breakdown, and how to get there from {starting_city}
- Format in clean markdown
"""

PLANNER_JSON_SCHEMA = """{
  "trip_title": "Catchy inspiring trip title",
  "overview": "2-3 vivid sentences painting the journey",
  "destinations": [
    {
      "name": "City or place name",
      "tagline": "Short evocative tagline e.g. The Pink City",
      "description": "2-3 sentences about why this place is special",
      "history": "1-2 fascinating sentences about the history or origin of this place",
      "unique_facts": ["Surprising fact 1", "Unique fact 2", "Interesting fact 3"],
      "fun_activities": ["Activity 1", "Activity 2", "Activity 3", "Activity 4"],
      "highlights": ["Landmark 1", "Landmark 2", "Landmark 3", "Landmark 4"]
    }
  ],
  "itinerary": [
    {
      "day": 1,
      "title": "Arrival and first impressions",
      "location": "City name",
      "fun_highlight": "Most exciting thing about today in one punchy sentence",
      "morning": "Detailed morning plan",
      "afternoon": "Detailed afternoon plan",
      "evening": "Evening plan",
      "stay": "City name where you sleep tonight (used for hotel lookup)"
    }
  ],
  "budget": {
    "transport": 15000,
    "accommodation": 20000,
    "food": 8000,
    "activities": 5000
  },
  "tips": ["Practical tip 1", "Practical tip 2", "Practical tip 3", "Practical tip 4"]
}"""

FLIGHT_OPTIONS_SCHEMA = """{
  "options": [
    {
      "airlines": "e.g. IndiGo / Air India / SpiceJet",
      "route": "e.g. Mumbai → Kochi",
      "duration": "e.g. 2h 15min",
      "cost_per_person": "e.g. ₹4,200",
      "class": "Economy",
      "booking_tip": "e.g. Book on MakeMyTrip 3-4 weeks ahead for best fares"
    }
  ]
}"""

TRAIN_OPTIONS_SCHEMA = """{
  "options": [
    {
      "name": "e.g. Kerala Express",
      "number": "e.g. 16343",
      "route": "e.g. Mumbai CST → Ernakulam Jn",
      "departure": "e.g. 09:30",
      "arrival": "e.g. 11:25+1",
      "duration": "e.g. 25h 55min",
      "sleeper": "e.g. ₹650",
      "third_ac": "e.g. ₹1,750",
      "second_ac": "e.g. ₹2,500",
      "frequency": "e.g. Daily / Mon, Wed, Fri",
      "booking_tip": "e.g. Book on irctc.co.in at least 3 weeks ahead"
    }
  ]
}"""

VEHICLE_OPTIONS_SCHEMA = """{
  "options": [
    {
      "vehicle_type": "e.g. Sedan (Swift Dzire) or SUV (Innova Crysta)",
      "cost_per_day": "e.g. ₹2,500 self-drive / ₹3,500 with driver",
      "fuel_estimate": "e.g. ₹4,000 for full trip",
      "total_estimate": "e.g. ₹21,500 for 7 days with driver",
      "booking_tip": "e.g. Zoomcar for self-drive; Savaari or local aggregators for chauffeur-driven"
    }
  ]
}"""

PLAN_JSON_SCHEMA = """{
  "trip_title": "Catchy inspiring trip title",
  "overview": "2-3 vivid sentences painting the journey",
  "destinations": [
    {
      "name": "City or place name",
      "tagline": "Short evocative tagline e.g. The Pink City",
      "description": "2-3 sentences about why this place is special",
      "history": "1-2 fascinating sentences about the history or origin of this place",
      "unique_facts": ["Surprising or little-known fact 1", "Unique fact 2", "Interesting fact 3"],
      "fun_activities": ["Thrilling or fun activity 1", "Activity 2", "Activity 3", "Activity 4"],
      "highlights": ["Top landmark 1", "Top landmark 2", "Top landmark 3", "Top landmark 4"]
    }
  ],
  "itinerary": [
    {
      "day": 1,
      "title": "Arrival and first impressions",
      "location": "City name",
      "fun_highlight": "The most exciting thing about today in one punchy sentence",
      "morning": "Detailed morning plan — what to visit, what to eat, practical tip",
      "afternoon": "Detailed afternoon plan — activities, sights, experiences",
      "evening": "Evening plan — sunset spot, dinner recommendation, nightlife or relaxation",
      "stay": "City name where you sleep tonight (used for hotel lookup — must match a destination name)"
    }
  ],
  "transport": {
    "flight": {
      "airlines": "e.g. IndiGo, Air India, SpiceJet",
      "route": "e.g. Mumbai → Jaipur",
      "duration": "e.g. 1h 50min",
      "cost_per_person": "e.g. ₹4,500",
      "booking_tip": "e.g. Book on MakeMyTrip or Cleartrip 3-4 weeks in advance for best fares"
    },
    "train": {
      "name": "e.g. Rajdhani Express / Mandore Express",
      "number": "e.g. 12957",
      "route": "e.g. Mumbai Central → Jaipur Junction",
      "duration": "e.g. 17h 30min",
      "cost_per_person": "e.g. ₹1,200 (Sleeper) / ₹2,800 (3AC) / ₹4,200 (2AC)",
      "booking_tip": "e.g. Book on IRCTC at least 3 weeks ahead; use Tatkal quota for last-minute"
    },
    "rented_vehicle": {
      "vehicle_type": "e.g. Sedan (Swift Dzire) or SUV (Toyota Innova)",
      "estimated_cost_per_day": "e.g. ₹2,500 self-drive / ₹3,500 with driver",
      "fuel_estimate": "e.g. ₹4,500 total for the trip",
      "total_estimate": "e.g. ₹22,000 for 7 days with driver",
      "booking_tip": "e.g. Book on Zoomcar for self-drive; use Savaari or local aggregators for chauffeur-driven"
    }
  },
  "budget": {
    "transport": 15000,
    "accommodation": 20000,
    "food": 8000,
    "activities": 5000
  },
  "tips": ["Practical tip 1", "Practical tip 2", "Practical tip 3", "Practical tip 4"]
}"""

HOTELS_JSON_SCHEMA = """{
  "hotels_by_location": {
    "City Name": [
      {
        "name": "Hotel name",
        "type": "Budget",
        "price_per_night": "₹1,500",
        "rating": "4.2/5",
        "why_pick": "Best value hotel close to the main market"
      },
      {
        "name": "Hotel name",
        "type": "Mid-range",
        "price_per_night": "₹4,500",
        "rating": "4.5/5",
        "why_pick": "Great amenities, pool, and central location"
      },
      {
        "name": "Hotel name",
        "type": "Luxury",
        "price_per_night": "₹12,000",
        "rating": "4.8/5",
        "why_pick": "Premium heritage experience with top-class service"
      }
    ]
  }
}"""

SUGGESTION_JSON_SCHEMA = """{
  "trip_title": "Catchy title e.g. Your Perfect Indian Getaway",
  "overview": "Why these 3 destinations suit this traveller — vivid 2-3 sentences",
  "destinations": [
    {
      "name": "City or region",
      "tagline": "Short evocative tagline",
      "description": "Why this destination is perfect for this traveller (2-3 sentences)",
      "history": "1-2 fascinating sentences about the history or origin",
      "unique_facts": ["Surprising fact 1", "Unique fact 2"],
      "fun_activities": ["Fun activity 1", "Activity 2", "Activity 3"],
      "highlights": ["Landmark 1", "Landmark 2", "Landmark 3"],
      "estimated_cost": "₹X,XXX total for the trip"
    }
  ],
  "itinerary": [
    {
      "day": 1,
      "title": "Option 1 – Day 1 title",
      "location": "City name",
      "fun_highlight": "Most exciting thing about today",
      "morning": "Morning plan",
      "afternoon": "Afternoon plan",
      "evening": "Evening plan",
      "stay": "Hotel area"
    }
  ],
  "hotels": [
    {
      "name": "Recommended hotel",
      "location": "City",
      "type": "Budget/Mid-range/Luxury",
      "price_per_night": "₹X,XXX",
      "why_pick": "Why this hotel suits the traveller"
    }
  ],
  "transport": {
    "flight": {"airlines": "Airlines serving the route", "route": "Origin → Destination", "duration": "e.g. 2h", "cost_per_person": "₹X,XXX", "booking_tip": "Booking advice"},
    "train": {"name": "Train name", "number": "Train number", "route": "Origin → Destination", "duration": "e.g. 12h", "cost_per_person": "₹X,XXX (class)", "booking_tip": "Booking advice"},
    "rented_vehicle": {"vehicle_type": "Sedan/SUV", "estimated_cost_per_day": "₹X,XXX", "fuel_estimate": "₹X,XXX", "total_estimate": "₹X,XXX for N days", "booking_tip": "Booking advice"}
  },
  "budget": {
    "transport": 15000,
    "accommodation": 20000,
    "food": 8000,
    "activities": 5000
  },
  "tips": ["Tip 1", "Tip 2", "Tip 3"]
}"""

CONFIRMATION_TEMPLATE = """\
Here's what I have so far:
 - Travelers: {travelers_summary}
 - Dates: {dates_summary}
 - From: {starting_city}
 - Budget: ₹{budget}
 - Vibe: {vibe}{kids_line}{constraints_line}{destination_line}

Does this look right? Anything to change?\
"""
