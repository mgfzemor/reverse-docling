from __future__ import annotations

import calendar
import datetime as dt
from typing import Any

from .base import BuildContext, DocType, make_brand, money, ref_code, today_like

# (i18n key under bank_statement.tx, direction, amount range as a fraction of monthly salary)
_TX_KINDS = [
    ("card", "debit", (0.002, 0.03), 10),
    ("grocery", "debit", (0.005, 0.04), 6),
    ("transfer_out", "debit", (0.01, 0.15), 3),
    ("transfer_in", "credit", (0.01, 0.2), 2),
    ("atm", "debit", (0.01, 0.06), 3),
    ("utility", "debit", (0.01, 0.04), 2),
    ("subscription", "debit", (0.001, 0.008), 2),
    ("fee", "debit", (0.0005, 0.002), 1),
]
_SALARY_BASE = {"USD": 5200, "SAR": 14000, "CNY": 12000, "RUB": 95000, "BRL": 6500, "EUR": 3200,
                "JPY": 380000, "INR": 85000}


class BankStatement(DocType):
    name = "bank_statement"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person, lang = ctx.rng, ctx.t, ctx.identity, ctx.lang
        brand = make_brand(t, "bank", rng)

        issued = today_like(rng)
        last_month_end = issued.replace(day=1) - dt.timedelta(days=1)
        start = last_month_end.replace(day=1)
        days_in_month = calendar.monthrange(start.year, start.month)[1]

        salary = round(_SALARY_BASE.get(lang.currency, 4000) * rng.uniform(0.5, 2.5), -1)
        balance = money(rng, salary * 0.1, salary * 3)
        opening = balance

        weights = [k[3] for k in _TX_KINDS]
        events: list[tuple[dt.date, str, str, float]] = [
            (start.replace(day=min(rng.choice([1, 25, 28]), days_in_month)), t("bank_statement.tx.salary",
             employer=person.employer), "credit", salary)]
        for _ in range(rng.randint(14, 55)):
            kind, direction, (lo, hi), _w = rng.choices(_TX_KINDS, weights=weights)[0]
            day = start + dt.timedelta(days=rng.randint(0, days_in_month - 1))
            merchant = rng.choice(t.list("bank_statement.merchants"))
            desc = t(f"bank_statement.tx.{kind}", merchant=merchant, ref=ref_code(rng, 6))
            events.append((day, desc, direction, money(rng, salary * lo, salary * hi)))
        events.sort(key=lambda e: e[0])

        transactions = []
        total_debit = total_credit = 0.0
        for day, desc, direction, amount in events:
            if direction == "debit":
                balance -= amount
                total_debit += amount
            else:
                balance += amount
                total_credit += amount
            transactions.append({
                "date": day, "description": desc, "reference": ref_code(rng, 10, "0123456789"),
                "debit": amount if direction == "debit" else None,
                "credit": amount if direction == "credit" else None,
                "balance": round(balance, 2),
            })

        return {
            "bank_name": brand.name,
            "bank_bic": ref_code(rng, 4, "ABCDEFGHIJKLMNOPQRSTUVWXYZ") + lang.babel_locale[-2:] + ref_code(rng, 2),
            "branch": person.address.city,
            "branch_code": ref_code(rng, 4, "0123456789"),
            "customer_number": ref_code(rng, 8, "0123456789"),
            "account_holder": person.full_name,
            "account_number": person.account_number,
            "iban": person.iban,
            "account_type": rng.choice(t.list("bank_statement.account_types")),
            "currency": lang.currency,
            "period_start": start,
            "period_end": last_month_end,
            "statement_date": issued,
            "statement_number": rng.randint(1, 240),
            "opening_balance": round(opening, 2),
            "closing_balance": round(balance, 2),
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "transactions": transactions,
            "_style": self.brand_style(brand),
        }


DOC_TYPE = BankStatement()
