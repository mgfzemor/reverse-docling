from __future__ import annotations

import datetime as dt
from typing import Any

from .base import BuildContext, DocType, make_brand, ref_code, today_like

# currency -> price per kWh
_TARIFF = {"USD": 0.17, "SAR": 0.18, "CNY": 0.56, "RUB": 6.2, "BRL": 0.85, "EUR": 0.32, "JPY": 31, "INR": 7.5}


class UtilityBill(DocType):
    name = "utility_bill"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person, lang = ctx.rng, ctx.t, ctx.identity, ctx.lang
        brand = make_brand(t, "utility", rng)
        issued = today_like(rng)
        period_end = issued - dt.timedelta(days=rng.randint(2, 8))
        period_start = period_end - dt.timedelta(days=rng.choice([29, 30, 31]))
        previous = rng.randint(1000, 90000)
        consumption = rng.randint(120, 1400)
        tariff = _TARIFF.get(lang.currency, 0.2) * rng.uniform(0.8, 1.25)

        energy = round(consumption * tariff, 2)
        fixed = round(energy * rng.uniform(0.05, 0.15), 2)
        network = round(energy * rng.uniform(0.1, 0.3), 2)
        lines = [
            {"label": t("utility_bill.lines.energy"), "detail": f"{consumption} kWh × {tariff:.4f}", "amount": energy},
            {"label": t("utility_bill.lines.network"), "detail": "", "amount": network},
            {"label": t("utility_bill.lines.fixed"), "detail": "", "amount": fixed},
        ]
        subtotal = round(sum(x["amount"] for x in lines), 2)
        tax_rate = rng.choice([0.05, 0.1, 0.15, 0.19, 0.2])
        tax = round(subtotal * tax_rate, 2)
        # last 6 months of consumption for the bar chart
        history = [max(60, int(consumption * rng.uniform(0.6, 1.4))) for _ in range(5)] + [consumption]
        return {
            "provider": brand.name,
            "provider_phone": f"{rng.randint(800, 899)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
            "account_number": ref_code(rng, 10, "0123456789"),
            "meter_number": ref_code(rng, 3, "ABCDEFGHJKLMNPRSTUVWXYZ") + ref_code(rng, 8, "0123456789"),
            "invoice_number": ref_code(rng, 12, "0123456789"),
            "customer_name": person.full_name,
            "service_address": person.address.one_line(),
            "issue_date": issued,
            "period_start": period_start,
            "period_end": period_end,
            "due_date": issued + dt.timedelta(days=rng.choice([14, 15, 21, 30])),
            "previous_reading": previous,
            "current_reading": previous + consumption,
            "consumption_kwh": consumption,
            "tariff": round(tariff, 4),
            "lines": lines,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax": tax,
            "total": round(subtotal + tax, 2),
            "currency": lang.currency,
            "history": history,
            "_style": self.brand_style(brand),
        }


DOC_TYPE = UtilityBill()
