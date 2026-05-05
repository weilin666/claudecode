import os
import re
from datetime import datetime
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OUTBOUND_DATES = ["2026-07-10", "2026-07-11", "2026-07-12"]
RETURN_DATES = ["2026-07-31", "2026-08-01", "2026-08-02"]
ORIGIN = "JFK"
DESTINATION = "HKG"
REFRESH_INTERVAL = 600  # seconds

AIRLINE_NAMES = {
    "CX": "Cathay Pacific",
    "UA": "United Airlines",
    "AA": "American Airlines",
    "DL": "Delta",
    "CA": "Air China",
    "MH": "Malaysia Airlines",
    "SQ": "Singapore Airlines",
    "JL": "Japan Airlines",
    "NH": "ANA",
    "KE": "Korean Air",
    "OZ": "Asiana Airlines",
    "EK": "Emirates",
    "QR": "Qatar Airways",
    "TG": "Thai Airways",
    "CI": "China Airlines",
    "BR": "EVA Air",
    "MF": "Xiamen Airlines",
    "HX": "Hong Kong Airlines",
    "HA": "Hawaiian Airlines",
    "AS": "Alaska Airlines",
}

_cache = {"data": None, "timestamp": None, "error": None}


def parse_duration(duration_str):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration_str)
    if match:
        hours = int(match.group(1) or 0)
        mins = int(match.group(2) or 0)
        return f"{hours}h {mins}m"
    return duration_str


def fmt_datetime(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return iso_str


def fetch_flights():
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None, "AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET not set. See .env.example."

    try:
        from amadeus import Client, ResponseError
    except ImportError:
        return None, "amadeus package not installed. Run: pip install amadeus"

    amadeus = Client(client_id=client_id, client_secret=client_secret)
    results = []
    errors = []

    for outbound in OUTBOUND_DATES:
        for return_date in RETURN_DATES:
            try:
                response = amadeus.shopping.flight_offers_search.get(
                    originLocationCode=ORIGIN,
                    destinationLocationCode=DESTINATION,
                    departureDate=outbound,
                    returnDate=return_date,
                    adults=1,
                    max=3,
                    currencyCode="USD",
                )
                for offer in response.data:
                    out_itin = offer["itineraries"][0]
                    ret_itin = offer["itineraries"][1]
                    out_segs = out_itin["segments"]
                    ret_segs = ret_itin["segments"]
                    codes = offer.get("validatingAirlineCodes", ["?"])
                    airline_name = ", ".join(
                        AIRLINE_NAMES.get(c, c) for c in codes
                    )
                    results.append(
                        {
                            "outbound_date": outbound,
                            "return_date": return_date,
                            "price": float(offer["price"]["total"]),
                            "currency": offer["price"]["currency"],
                            "airline": airline_name,
                            "airline_codes": codes,
                            "outbound_duration": parse_duration(out_itin["duration"]),
                            "return_duration": parse_duration(ret_itin["duration"]),
                            "outbound_stops": len(out_segs) - 1,
                            "return_stops": len(ret_segs) - 1,
                            "depart_at": fmt_datetime(out_segs[0]["departure"]["at"]),
                            "arrive_at": fmt_datetime(out_segs[-1]["arrival"]["at"]),
                            "return_depart_at": fmt_datetime(ret_segs[0]["departure"]["at"]),
                            "return_arrive_at": fmt_datetime(ret_segs[-1]["arrival"]["at"]),
                        }
                    )
            except ResponseError as e:
                errors.append(f"{outbound}→{return_date}: {e.description}")

    results.sort(key=lambda x: x["price"])
    return results, "; ".join(errors) if errors else None


@app.route("/")
def index():
    return render_template(
        "airfare.html",
        origin=ORIGIN,
        destination=DESTINATION,
        refresh_interval=REFRESH_INTERVAL,
    )


@app.route("/api/flights")
def api_flights():
    global _cache
    now = datetime.now()

    if (
        _cache["data"] is not None
        and _cache["timestamp"] is not None
        and (now - _cache["timestamp"]).total_seconds() < REFRESH_INTERVAL
    ):
        return jsonify(
            {
                "results": _cache["data"],
                "last_updated": _cache["timestamp"].isoformat(),
                "cached": True,
                "error": _cache["error"],
            }
        )

    results, error = fetch_flights()
    _cache["data"] = results or []
    _cache["timestamp"] = now
    _cache["error"] = error

    return jsonify(
        {
            "results": _cache["data"],
            "last_updated": now.isoformat(),
            "cached": False,
            "error": error,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
