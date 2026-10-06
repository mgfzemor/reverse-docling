from __future__ import annotations

import datetime as dt
from typing import Any

from .base import BuildContext, DocType, make_brand, money, ref_code, today_like

AIRPORTS = ["JFK", "LAX", "LHR", "CDG", "FRA", "MAD", "DXB", "RUH", "JED", "SVO", "PEK", "PVG", "NRT", "GRU",
            "DEL", "BOM"]
# Rough block times in hours between "regions", good enough for plausible schedules.
_REGION = {"JFK": "am", "LAX": "am", "GRU": "sa", "LHR": "eu", "CDG": "eu", "FRA": "eu", "MAD": "eu",
           "SVO": "eu", "DXB": "me", "RUH": "me", "JED": "me", "PEK": "as", "PVG": "as", "NRT": "as",
           "DEL": "in", "BOM": "in"}
_HOURS = {frozenset(["am"]): 5, frozenset(["eu"]): 2.5, frozenset(["me"]): 1.8, frozenset(["as"]): 3,
          frozenset(["in"]): 2, frozenset(["sa"]): 3, frozenset(["am", "eu"]): 8, frozenset(["am", "sa"]): 10,
          frozenset(["eu", "me"]): 6.5, frozenset(["eu", "as"]): 11, frozenset(["eu", "in"]): 9,
          frozenset(["eu", "sa"]): 12, frozenset(["me", "as"]): 8, frozenset(["me", "in"]): 3.5,
          frozenset(["as", "in"]): 6, frozenset(["am", "as"]): 13, frozenset(["am", "me"]): 13,
          frozenset(["am", "in"]): 15, frozenset(["me", "sa"]): 14.5, frozenset(["as", "sa"]): 24,
          frozenset(["in", "sa"]): 20}
_HOME = {"en": "JFK", "ar": "RUH", "zh": "PEK", "ru": "SVO", "pt": "GRU", "es": "MAD", "fr": "CDG",
         "de": "FRA", "ja": "NRT", "hi": "DEL"}
_FARE_BASE = {"USD": 450, "SAR": 1800, "CNY": 3500, "RUB": 40000, "BRL": 2500, "EUR": 400, "JPY": 70000,
              "INR": 30000}


def block_hours(a: str, b: str) -> float:
    return _HOURS.get(frozenset([_REGION[a], _REGION[b]]), 8)


class FlightTicket(DocType):
    name = "flight_ticket"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person, lang = ctx.rng, ctx.t, ctx.identity, ctx.lang
        brand = make_brand(t, "airline", rng)
        code = ref_code(rng, 2, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        issued = today_like(rng)

        origin = _HOME.get(lang.code, "JFK") if rng.random() < 0.7 else rng.choice(AIRPORTS)
        dest = rng.choice([a for a in AIRPORTS if a != origin])
        depart_day = issued + dt.timedelta(days=rng.randint(3, 90))
        round_trip = rng.random() < 0.6
        cabin_key = rng.choices(["economy", "premium", "business", "first"], weights=[70, 12, 15, 3])[0]

        def segment(a: str, b: str, day: dt.date) -> dict[str, Any]:
            dep = dt.datetime.combine(day, dt.time(rng.randint(0, 23), rng.choice([0, 5, 15, 25, 35, 40, 50])))
            arr = dep + dt.timedelta(hours=block_hours(a, b), minutes=rng.randint(-20, 40))
            return {
                "flight": f"{code}{rng.randint(10, 9899)}", "from_code": a, "to_code": b,
                "from_city": t(f"airports.{a}"), "to_city": t(f"airports.{b}"),
                "departure": dep, "arrival": arr, "terminal": rng.choice(["1", "2", "3", "A", "B", "C", "N", "S"]),
                "gate": f"{rng.choice('ABCDEFG')}{rng.randint(1, 60)}",
                "seat": f"{rng.randint(1, 45)}{rng.choice('ABCDEFHJK')}",
                "boarding": dep - dt.timedelta(minutes=rng.choice([30, 40, 45, 60])),
                "cabin": t(f"flight_ticket.cabins.{cabin_key}"),
                "booking_class": rng.choice("YBMHKQLVJCDZF"),
                "baggage": f"{rng.choice([1, 1, 2])}PC" if rng.random() < 0.6 else f"{rng.choice([20, 23, 30, 40])}KG",
                "status": "OK",
            }

        segments = [segment(origin, dest, depart_day)]
        if round_trip:
            segments.append(segment(dest, origin, depart_day + dt.timedelta(days=rng.randint(2, 21))))

        multiplier = {"economy": 1, "premium": 1.8, "business": 4, "first": 7}[cabin_key]
        fare = round(_FARE_BASE.get(lang.currency, 400) * multiplier * rng.uniform(0.6, 1.6) * len(segments), 0)
        taxes = round(fare * rng.uniform(0.08, 0.3), 2)
        return {
            "airline": brand.name,
            "airline_code": code,
            "pnr": ref_code(rng, 6, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"),
            "ticket_number": f"{rng.randint(100, 999)}-{rng.randint(10**9, 10**10 - 1)}",
            "passenger_name": person.latin_name,
            "passenger_native_name": person.full_name,
            "frequent_flyer": f"{code}{rng.randint(10**7, 10**8 - 1)}" if rng.random() < 0.4 else None,
            "issue_date": issued,
            "issuing_office": t(f"airports.{origin}"),
            "segments": segments,
            "round_trip": round_trip,
            "fare": fare,
            "taxes": taxes,
            "total": round(fare + taxes, 2),
            "currency": lang.currency,
            "payment": rng.choice(t.list("flight_ticket.payment_methods")),
            "_style": self.brand_style(brand),
        }


DOC_TYPE = FlightTicket()
