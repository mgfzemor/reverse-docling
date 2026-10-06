from __future__ import annotations

import datetime as dt
from typing import Any

from .base import BuildContext, DocType, make_brand, ref_code, today_like
from .flight_ticket import AIRPORTS

_RATE_BASE = {"USD": 160, "SAR": 600, "CNY": 900, "RUB": 9000, "BRL": 550, "EUR": 140, "JPY": 22000,
              "INR": 7000}


class HotelReservation(DocType):
    name = "hotel_reservation"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person, lang = ctx.rng, ctx.t, ctx.identity, ctx.lang
        brand = make_brand(t, "hotel", rng)
        booked = today_like(rng)
        check_in = booked + dt.timedelta(days=rng.randint(2, 120))
        nights = rng.choice([1, 1, 2, 2, 3, 3, 4, 5, 7, 10])
        check_out = check_in + dt.timedelta(days=nights)
        room_key = rng.choice(["standard", "deluxe", "twin", "suite", "family"])
        rate = round(_RATE_BASE.get(lang.currency, 150) * rng.uniform(0.6, 2.2)
                     * {"standard": 1, "deluxe": 1.4, "twin": 1.1, "suite": 2.5, "family": 1.8}[room_key], 0)
        subtotal = rate * nights
        tax_rate = rng.choice([0.05, 0.08, 0.1, 0.12, 0.15])
        taxes = round(subtotal * tax_rate, 2)
        city_code = rng.choice(AIRPORTS)
        return {
            "hotel_name": brand.name,
            "hotel_city": t(f"airports.{city_code}"),
            "hotel_address": f"{rng.randint(1, 400)}, {rng.choice(t.list('hotel_reservation.streets'))}",
            "hotel_phone": f"+{rng.randint(1, 98)} {rng.randint(100, 999)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
            "stars": rng.choice([3, 4, 4, 5]),
            "confirmation_number": ref_code(rng, rng.choice([8, 9, 10]), "0123456789"),
            "booking_reference": ref_code(rng, 6),
            "booking_date": booked,
            "guest_name": person.full_name,
            "guest_email": person.email,
            "guest_phone": person.phone,
            "adults": rng.choice([1, 1, 2, 2, 2, 3]),
            "children": rng.choice([0, 0, 0, 1, 2]),
            "check_in": check_in,
            "check_out": check_out,
            "check_in_time": dt.time(rng.choice([14, 15, 16]), 0),
            "check_out_time": dt.time(rng.choice([10, 11, 12]), 0),
            "nights": nights,
            "rooms": 1 if room_key != "family" else rng.choice([1, 2]),
            "room_type": t(f"hotel_reservation.rooms.{room_key}"),
            "board": rng.choice(t.list("hotel_reservation.boards")),
            "rate_per_night": rate,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "taxes": taxes,
            "total": round(subtotal + taxes, 2),
            "currency": lang.currency,
            "paid": rng.random() < 0.5,
            "free_cancellation_until": check_in - dt.timedelta(days=rng.choice([1, 2, 3, 7])),
            "_style": self.brand_style(brand),
        }


DOC_TYPE = HotelReservation()
