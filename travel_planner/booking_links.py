"""Generate real booking-platform deep links from TripContext."""

import re
from datetime import date, datetime, timedelta
from typing import List

from .models import TripContext

IATA = {
    "mumbai": "BOM", "delhi": "DEL", "new delhi": "DEL",
    "bangalore": "BLR", "bengaluru": "BLR",
    "chennai": "MAA", "kolkata": "CCU", "calcutta": "CCU",
    "hyderabad": "HYD", "goa": "GOI",
    "jaipur": "JAI", "ahmedabad": "AMD", "pune": "PNQ",
    "kochi": "COK", "cochin": "COK",
    "lucknow": "LKO", "varanasi": "VNS",
    "amritsar": "ATQ", "srinagar": "SXR",
    "leh": "IXL", "udaipur": "UDR",
    "jodhpur": "JDH", "nagpur": "NAG",
    "guwahati": "GAU", "patna": "PAT",
    "bhopal": "BHO", "bhubaneswar": "BBI",
    "mangalore": "IXE", "coimbatore": "CJB",
    "thiruvananthapuram": "TRV", "trivandrum": "TRV",
    "vizag": "VTZ", "visakhapatnam": "VTZ",
    "jammu": "IXJ", "bagdogra": "IXB",
    "port blair": "IXZ", "ranchi": "IXR",
    "indore": "IDR", "raipur": "RPR",
    "chandigarh": "IXC", "dehradun": "DED",
}

STATION = {
    "mumbai": "CSTM", "delhi": "NDLS", "new delhi": "NDLS",
    "bangalore": "SBC", "bengaluru": "SBC",
    "chennai": "MAS", "kolkata": "KOAA", "calcutta": "KOAA",
    "hyderabad": "HYB", "goa": "MAO",
    "jaipur": "JP", "ahmedabad": "ADI", "pune": "PUNE",
    "kochi": "ERS", "cochin": "ERS",
    "lucknow": "LKO", "varanasi": "BSB",
    "amritsar": "ASR", "udaipur": "UDZ",
    "jodhpur": "JU", "nagpur": "NGP",
    "guwahati": "GHY", "patna": "PNBE",
    "bhopal": "BPL", "bhubaneswar": "BBS",
    "visakhapatnam": "VSKP", "vizag": "VSKP",
    "mangalore": "MAQ", "coimbatore": "CBE",
    "thiruvananthapuram": "TVC", "trivandrum": "TVC",
    "ranchi": "RNC", "indore": "INDB",
    "chandigarh": "CDG", "dehradun": "DDN",
}

ZOOMCAR_CITY = {
    "mumbai": "mumbai", "delhi": "delhi", "new delhi": "delhi",
    "bangalore": "bangalore", "bengaluru": "bangalore",
    "chennai": "chennai", "kolkata": "kolkata", "calcutta": "kolkata",
    "hyderabad": "hyderabad", "goa": "goa",
    "jaipur": "jaipur", "ahmedabad": "ahmedabad", "pune": "pune",
    "kochi": "kochi", "cochin": "kochi",
    "coimbatore": "coimbatore", "chandigarh": "chandigarh",
    "lucknow": "lucknow", "indore": "indore", "nagpur": "nagpur",
    "surat": "surat", "vadodara": "vadodara",
}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def _ck(city: str) -> str:
    return (city or "").lower().strip()


def _parse_date(ctx: TripContext) -> date:
    """Best-guess departure date from TripContext; defaults to 60 days from today."""
    today = date.today()
    raw = (ctx.travel_dates or ctx.travel_month or "").strip()
    if not raw:
        return today + timedelta(days=60)

    # Explicit date formats: "2024-12-01", "01/12/2024", "1 December 2024", "December 1, 2024"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y"):
        try:
            candidate = raw.split("–")[0].split("to")[0].strip()
            # take only the date-like prefix
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            pass

    # Range: "December 1-5, 2024" or "Dec 1–5 2024"
    m = re.search(r"(\w+)\s+(\d{1,2})[\s,–\-]+\d{1,2},?\s*(\d{4})", raw)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(2)))
            except ValueError:
                pass

    # "Month Year" or just "Month"
    m = re.search(r"(\w+)\s*(\d{4})?", raw)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        year = int(m.group(2)) if m.group(2) else today.year
        if mon:
            try:
                d = date(year, mon, 15)
                if d < today:
                    d = date(year + 1, mon, 15)
                low = raw.lower()
                if any(x in low for x in ("first week", "early", "beginning")):
                    d = d.replace(day=1)
                elif any(x in low for x in ("late", "end", "last week")):
                    d = d.replace(day=25)
                return d
            except ValueError:
                pass

    return today + timedelta(days=60)


def flight_links(ctx: TripContext) -> List[dict]:
    fc = IATA.get(_ck(ctx.starting_city), "")
    tc = IATA.get(_ck(ctx.destination), "")
    dep = _parse_date(ctx)
    n = ctx.num_travelers or 1

    if not (fc and tc):
        return [{"label": "MakeMyTrip", "url": "https://www.makemytrip.com/flights/"}]

    mmt_date = dep.strftime("%d%m%Y")
    gb_date  = dep.strftime("%Y%m%d")
    ct_date  = dep.strftime("%d/%m/%Y")

    return [
        {
            "label": "MakeMyTrip",
            "url": (
                f"https://www.makemytrip.com/flight/search"
                f"?tripType=O&itinerary={fc}-{tc}-{mmt_date}"
                f"&paxType=A-{n}_C-0_I-0&cabinClass=E&ccde=IN&lang=eng"
            ),
        },
        {
            "label": "Goibibo",
            "url": (
                f"https://www.goibibo.com/flights/search/"
                f"?traveldate={gb_date}&source={fc}&destination={tc}"
                f"&class=E&adults={n}&children=0&infants=0&travelType=D"
            ),
        },
        {
            "label": "Cleartrip",
            "url": (
                f"https://www.cleartrip.com/flights/results/"
                f"?from={fc}&to={tc}&depart_date={ct_date}"
                f"&adults={n}&childs=0&infants=0&class=Economy&intl=n"
            ),
        },
    ]


def train_links(ctx: TripContext) -> List[dict]:
    fc = STATION.get(_ck(ctx.starting_city), "")
    tc = STATION.get(_ck(ctx.destination), "")
    dep = _parse_date(ctx)
    n = ctx.num_travelers or 1

    links: List[dict] = [
        {"label": "IRCTC", "url": "https://www.irctc.co.in/nget/train-search"},
    ]

    if fc and tc:
        ix_date = dep.strftime("%Y%m%d")
        links.append({
            "label": "ixigo",
            "url": f"https://www.ixigo.com/search/result/train/{fc}/{tc}/{ix_date}/{n}/0/0/all",
        })
        links.append({
            "label": "RailYatri",
            "url": (
                f"https://www.railyatri.in/trains-between-stations"
                f"?from_code={fc}&to_code={tc}&date={dep.isoformat()}"
            ),
        })

    return links


def hotel_links(ctx: TripContext, city: str) -> List[dict]:
    dep    = _parse_date(ctx)
    nights = ctx.duration_days or 2
    co     = dep + timedelta(days=nights)
    n      = ctx.num_travelers or 2
    city_q = city.replace(" ", "+")
    city_enc = city.replace(" ", "%20")

    return [
        {
            "label": "Booking.com",
            "url": (
                f"https://www.booking.com/searchresults.html"
                f"?ss={city_q}+India&checkin={dep.isoformat()}"
                f"&checkout={co.isoformat()}&group_adults={n}&no_rooms=1&lang=en-gb"
            ),
        },
        {
            "label": "MakeMyTrip",
            "url": (
                f"https://www.makemytrip.com/hotels/hotel-listing/"
                f"?checkin={dep.strftime('%m%d%Y')}&checkout={co.strftime('%m%d%Y')}"
                f"&city={city_enc}&roomCount=1&adultsCount={n}&childCount=0"
            ),
        },
        {
            "label": "Airbnb",
            "url": (
                f"https://www.airbnb.co.in/s/{city_enc}--India/homes"
                f"?checkin={dep.isoformat()}&checkout={co.isoformat()}&adults={n}"
            ),
        },
    ]


def vehicle_links(ctx: TripContext) -> List[dict]:
    dest_key  = _ck(ctx.destination or "")
    from_city = (ctx.starting_city or "").lower().replace(" ", "-")
    to_city   = (ctx.destination   or "").lower().replace(" ", "-")
    zoom_slug = ZOOMCAR_CITY.get(dest_key, to_city)
    dep       = _parse_date(ctx)

    return [
        {
            "label": "Zoomcar",
            "url": f"https://www.zoomcar.com/{zoom_slug}",
        },
        {
            "label": "Savaari",
            "url": f"https://www.savaari.com/outstation-cabs/{from_city}-to-{to_city}",
        },
        {
            "label": "MakeMyTrip Cabs",
            "url": (
                f"https://www.makemytrip.com/cab/search"
                f"?type=OW&from={ctx.starting_city or ''}"
                f"&to={ctx.destination or ''}&cab=sedan"
                f"&date={dep.strftime('%d/%m/%Y')}"
            ),
        },
    ]
