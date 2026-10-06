from __future__ import annotations

import calendar
import datetime as dt
from typing import Any

from .bank_statement import _SALARY_BASE
from .base import BuildContext, DocType, make_brand, ref_code, today_like


class Payslip(DocType):
    name = "payslip"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person, lang = ctx.rng, ctx.t, ctx.identity, ctx.lang
        brand = make_brand(t, "company", rng)
        employer = person.employer or brand.name
        issued = today_like(rng)
        period_start = issued.replace(day=1)
        period_end = period_start.replace(day=calendar.monthrange(issued.year, issued.month)[1])
        base = round(_SALARY_BASE.get(lang.currency, 4000) * rng.uniform(0.6, 2.8), -1)

        earnings = [{"label": t("payslip.earnings.basic"), "amount": base}]
        if rng.random() < 0.6:
            earnings.append({"label": t("payslip.earnings.housing"), "amount": round(base * rng.uniform(0.05, 0.25), 2)})
        if rng.random() < 0.5:
            earnings.append({"label": t("payslip.earnings.transport"), "amount": round(base * rng.uniform(0.02, 0.08), 2)})
        if rng.random() < 0.35:
            earnings.append({"label": t("payslip.earnings.overtime"), "amount": round(base * rng.uniform(0.03, 0.15), 2)})
        if rng.random() < 0.15:
            earnings.append({"label": t("payslip.earnings.bonus"), "amount": round(base * rng.uniform(0.1, 0.5), 2)})
        gross = round(sum(e["amount"] for e in earnings), 2)

        deductions = [
            {"label": t("payslip.deductions.income_tax"), "amount": round(gross * rng.uniform(0.0, 0.25), 2)},
            {"label": t("payslip.deductions.social_security"), "amount": round(gross * rng.uniform(0.04, 0.1), 2)},
        ]
        if rng.random() < 0.6:
            deductions.append({"label": t("payslip.deductions.pension"), "amount": round(gross * rng.uniform(0.02, 0.06), 2)})
        if rng.random() < 0.5:
            deductions.append({"label": t("payslip.deductions.health"), "amount": round(gross * rng.uniform(0.01, 0.04), 2)})
        total_deductions = round(sum(d["amount"] for d in deductions), 2)
        net = round(gross - total_deductions, 2)
        months = issued.month
        return {
            "employer": employer,
            "employer_address": f"{rng.randint(1, 300)}, {rng.choice(t.list('hotel_reservation.streets'))}, {person.address.city}",
            "employer_tax_id": ref_code(rng, 10, "0123456789"),
            "employee_name": person.full_name,
            "employee_id": ref_code(rng, 6, "0123456789"),
            "employee_tax_id": person.id_number,
            "job_title": person.job_title,
            "department": rng.choice(t.list("payslip.departments")),
            "hire_date": issued - dt.timedelta(days=rng.randint(60, 4000)),
            "period_start": period_start,
            "period_end": period_end,
            "pay_date": period_end - dt.timedelta(days=rng.choice([0, 0, 2, 5])),
            "bank_account": person.iban or person.account_number,
            "earnings": earnings,
            "deductions": deductions,
            "gross": gross,
            "total_deductions": total_deductions,
            "net": net,
            "ytd_gross": round(gross * months * rng.uniform(0.95, 1.02), 2),
            "ytd_net": round(net * months * rng.uniform(0.95, 1.02), 2),
            "currency": lang.currency,
            "_style": self.brand_style(brand),
        }


DOC_TYPE = Payslip()
