from __future__ import annotations

import datetime as dt
from typing import Any

from anyascii import anyascii

from .base import BuildContext, DocType, make_brand, ref_code, today_like

def _slug(name: str) -> str:
    return "".join(c for c in anyascii(name).lower() if c.isalnum())[:20] or "company"


_PRICE_SCALE ={"USD": 1, "SAR": 3.75, "CNY": 7.2, "RUB": 90, "BRL": 5.2, "EUR": 0.92, "JPY": 150, "INR": 83}


class Invoice(DocType):
    name = "invoice"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person, lang = ctx.rng, ctx.t, ctx.identity, ctx.lang
        brand = make_brand(t, "company", rng)
        issued = today_like(rng)
        scale = _PRICE_SCALE.get(lang.currency, 1)
        tax_rate = rng.choice([0.0, 0.05, 0.1, 0.13, 0.15, 0.19, 0.2])

        catalog = t.list("invoice.items")
        items = []
        for name in rng.sample(catalog, k=rng.randint(1, min(7, len(catalog)))):
            qty = rng.choice([1, 1, 1, 2, 3, 5, 10])
            unit = round(rng.uniform(15, 900) * scale, 2)
            items.append({"description": name, "quantity": qty, "unit_price": unit, "amount": round(qty * unit, 2)})
        subtotal = round(sum(i["amount"] for i in items), 2)
        discount = round(subtotal * rng.choice([0, 0, 0, 0.05, 0.1]), 2)
        tax = round((subtotal - discount) * tax_rate, 2)
        return {
            "seller": brand.name,
            "seller_address": f"{rng.randint(1, 500)}, {rng.choice(t.list('hotel_reservation.streets'))}",
            "seller_tax_id": ref_code(rng, 11, "0123456789"),
            "seller_email": f"billing@{_slug(brand.name)}.example.com",
            "seller_iban": ref_code(rng, 2, "ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ref_code(rng, 20, "0123456789"),
            "buyer_name": person.full_name,
            "buyer_address": person.address.one_line(),
            "buyer_email": person.email,
            "invoice_number": f"{issued.year}-{rng.randint(1, 99999):05d}",
            "order_number": ref_code(rng, 8),
            "issue_date": issued,
            "due_date": issued + dt.timedelta(days=rng.choice([0, 7, 14, 30, 45])),
            "line_items": items,
            "subtotal": subtotal,
            "discount": discount,
            "tax_rate": tax_rate,
            "tax": tax,
            "total": round(subtotal - discount + tax, 2),
            "currency": lang.currency,
            "paid": rng.random() < 0.4,
            "_style": self.brand_style(brand),
        }


DOC_TYPE = Invoice()
