from __future__ import annotations

import datetime as dt
import math
import random
from typing import Any

from markupsafe import Markup

from .base import BuildContext, DocType, ref_code


def seal_svg(color: str, rng: random.Random, size: int = 110) -> Markup:
    """A generic official-looking seal: concentric rings, dashes and a star. Not any real emblem."""
    c = size / 2
    points = []
    n = rng.choice([5, 6, 8])
    for i in range(n * 2):
        r = (c * 0.32) if i % 2 == 0 else (c * 0.14)
        a = math.pi * i / n - math.pi / 2
        points.append(f"{c + r * math.cos(a):.1f},{c + r * math.sin(a):.1f}")
    return Markup(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'opacity=".75"><g fill="none" stroke="{color}">'
        f'<circle cx="{c}" cy="{c}" r="{c - 3}" stroke-width="2.5"/>'
        f'<circle cx="{c}" cy="{c}" r="{c - 9}" stroke-width="1" stroke-dasharray="3 3"/>'
        f'<circle cx="{c}" cy="{c}" r="{c * 0.5}" stroke-width="1.5"/></g>'
        f'<polygon points="{" ".join(points)}" fill="{color}"/></svg>'
    )


class BirthCertificate(DocType):
    name = "birth_certificate"

    def build(self, ctx: BuildContext) -> dict[str, Any]:
        rng, t, person = ctx.rng, ctx.t, ctx.identity
        dob = person.date_of_birth
        registered = dob + dt.timedelta(days=rng.randint(2, 40))
        issued = registered + dt.timedelta(days=rng.randint(0, (dt.date(2026, 9, 1) - registered).days))
        color = rng.choice(["#1e3a8a", "#7f1d1d", "#14532d", "#4a044e", "#374151"])
        return {
            "registry": rng.choice(t.list("brands.registry")),
            "district": person.place_of_birth,
            "certificate_number": f"{ref_code(rng, 2, 'ABCDEFGHJKLMNPRSTUVWXYZ')}-{rng.randint(10**6, 10**7 - 1)}",
            "registration_number": f"{dob.year}/{rng.randint(1, 99999):05d}",
            "child_name": person.full_name,
            "child_latin_name": person.latin_name,
            "sex": t(f"birth_certificate.{person.gender}"),
            "date_of_birth": dob,
            "time_of_birth": dt.time(rng.randint(0, 23), rng.randint(0, 59)),
            "place_of_birth": person.place_of_birth,
            "hospital": rng.choice(t.list("birth_certificate.hospitals")),
            "father_name": person.father_name,
            "father_nationality": person.nationality,
            "mother_name": person.mother_name,
            "mother_nationality": person.nationality,
            "registration_date": registered,
            "issue_date": issued,
            "registrar": rng.choice(t.list("birth_certificate.registrar_titles")),
            "_style": {"primary": color, "seal": seal_svg(color, rng)},
        }


DOC_TYPE = BirthCertificate()
