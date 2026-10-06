"""Build complete identities: manual values win, Faker fills the gaps per language."""

from __future__ import annotations

import datetime as dt
import hashlib
import random
import string

from anyascii import anyascii
from babel import Locale
from faker import Faker

from .locales import Language
from .models import Address, Identity, IdentitySpec

# --- Curated Arabic data: Faker's ar_SA has no address provider and anyascii drops short vowels. ---
_SA_CITIES = {
    "الرياض": "منطقة الرياض", "جدة": "منطقة مكة المكرمة", "مكة المكرمة": "منطقة مكة المكرمة",
    "المدينة المنورة": "منطقة المدينة المنورة", "الدمام": "المنطقة الشرقية", "الخبر": "المنطقة الشرقية",
    "الطائف": "منطقة مكة المكرمة", "تبوك": "منطقة تبوك", "أبها": "منطقة عسير", "بريدة": "منطقة القصيم",
}
_SA_STREETS = ["الملك فهد", "الأمير سلطان", "العليا", "التحلية", "الملك عبدالعزيز", "الأمير محمد بن عبدالعزيز",
               "الستين", "الخليج", "الملك فيصل", "عمر بن الخطاب"]
_AR_MALE = [("محمد", "Mohammed"), ("أحمد", "Ahmed"), ("عبدالله", "Abdullah"), ("خالد", "Khalid"),
            ("فهد", "Fahad"), ("سلطان", "Sultan"), ("عمر", "Omar"), ("يوسف", "Yousef"), ("فيصل", "Faisal"),
            ("ناصر", "Nasser"), ("سعود", "Saud"), ("ماجد", "Majed"), ("تركي", "Turki"), ("عبدالرحمن", "Abdulrahman"),
            ("إبراهيم", "Ibrahim"), ("حسن", "Hassan"), ("علي", "Ali"), ("طارق", "Tariq"), ("بندر", "Bandar")]
_AR_FEMALE = [("فاطمة", "Fatimah"), ("نورة", "Noura"), ("سارة", "Sarah"), ("مريم", "Maryam"), ("ريم", "Reem"),
              ("هند", "Hind"), ("لطيفة", "Latifa"), ("أمل", "Amal"), ("منى", "Mona"), ("دانة", "Dana"),
              ("لينا", "Lina"), ("عائشة", "Aisha"), ("جواهر", "Jawaher"), ("شهد", "Shahad"), ("هيفاء", "Haifa")]
_AR_FAMILY = [("العتيبي", "Al-Otaibi"), ("القحطاني", "Al-Qahtani"), ("الغامدي", "Al-Ghamdi"),
              ("الشمري", "Al-Shammari"), ("الدوسري", "Al-Dosari"), ("الزهراني", "Al-Zahrani"),
              ("الحربي", "Al-Harbi"), ("المطيري", "Al-Mutairi"), ("السبيعي", "Al-Subaie"), ("العنزي", "Al-Anazi"),
              ("الشهري", "Al-Shehri"), ("المالكي", "Al-Malki"), ("السلمي", "Al-Sulami"), ("البقمي", "Al-Buqami")]
_AR_JOBS = ["مهندس مدني", "محاسب", "طبيب", "معلم", "مدير مشاريع", "مبرمج", "صيدلي", "محامي",
            "مسؤول مبيعات", "أخصائي موارد بشرية", "فني كهرباء", "مستشار مالي"]

# Total IBAN length per country (ISO 13616); countries without IBAN use account numbers only.
_IBAN_LENGTHS = {"SA": 24, "RU": 33, "BR": 29, "ES": 24, "FR": 27, "DE": 22}

_FAMILY_FIRST = {"zh", "ja"}
_LATIN_SCRIPT = {"en", "pt", "es", "fr", "de"}


def _iban(country: str, rng: random.Random) -> str | None:
    length = _IBAN_LENGTHS.get(country)
    if not length:
        return None
    bban = "".join(rng.choice(string.digits) for _ in range(length - 4))
    numeric = "".join(str(int(c, 36)) for c in bban + country + "00")
    check = 98 - int(numeric) % 97
    return f"{country}{check:02d}{bban}"


def _account_number(rng: random.Random) -> str:
    return "".join(rng.choice(string.digits) for _ in range(rng.choice([10, 12, 14])))


def _territory(lang: Language) -> str:
    return lang.babel_locale.split("_")[-1]


def country_name(lang: Language) -> str:
    return Locale.parse(lang.babel_locale).territories.get(_territory(lang), _territory(lang))


def _random_address(fake: Faker, lang: Language, rng: random.Random) -> Address:
    country = country_name(lang)
    if lang.code == "ar":
        city = rng.choice(list(_SA_CITIES))
        return Address(street=f"شارع {rng.choice(_SA_STREETS)}", building_number=str(rng.randint(1000, 9999)),
                       city=city, state=_SA_CITIES[city], postcode=f"{rng.randint(11000, 34999)}", country=country)
    if lang.code == "ja":
        return Address(street=f"{fake.town()}{fake.chome()}{fake.ban()}", building_number=fake.gou(),
                       city=fake.city(), state=fake.prefecture(), postcode=fake.postcode(), country=country)
    if lang.code == "zh":
        return Address(street=fake.street_name(), building_number=f"{rng.randint(1, 999)}号",
                       city=fake.city(), state=fake.province(), postcode=fake.postcode(), country=country)
    try:
        state = fake.state()
    except AttributeError:
        state = fake.administrative_unit()
    return Address(street=fake.street_name(), building_number=fake.building_number(), city=fake.city(),
                   state=state, postcode=fake.postcode(), country=country)


def _ru_surname(surname: str, gender: str) -> str:
    """Russian surnames agree with gender: Блохина (f) <-> Блохин (m)."""
    male_endings = ("ов", "ев", "ин", "ын")
    if gender == "male" and surname.endswith(tuple(e + "а" for e in male_endings)):
        return surname[:-1]
    if gender == "female" and surname.endswith(male_endings):
        return surname + "а"
    return surname


class _Names:
    """Generates (native, latin) name parts that stay consistent with each other."""

    def __init__(self, fake: Faker, lang: Language, rng: random.Random):
        self.fake, self.lang, self.rng = fake, lang, rng

    def given(self, gender: str) -> tuple[str, str]:
        f, code = self.fake, self.lang.code
        if code == "ar":
            return self.rng.choice(_AR_MALE if gender == "male" else _AR_FEMALE)
        if code == "ja":
            kanji, _, roman = f.first_name_male_pair() if gender == "male" else f.first_name_female_pair()
            return kanji, roman
        name = f.first_name_male() if gender == "male" else f.first_name_female()
        return name, anyascii(name)

    def family(self) -> tuple[str, str]:
        f, code = self.fake, self.lang.code
        if code == "ar":
            return self.rng.choice(_AR_FAMILY)
        if code == "ja":
            kanji, _, roman = f.last_name_pair()
            return kanji, roman
        name = f.last_name_male() if code == "ru" else f.last_name()
        return name, anyascii(name)

    def display(self, given: str, family: str, gender: str, patronymic: str | None = None) -> str:
        if self.lang.code in _FAMILY_FIRST:
            return f"{family}{given}"
        if self.lang.code == "ru":
            return " ".join(p for p in (_ru_surname(family, gender), given, patronymic) if p)
        return f"{given} {family}"


def build_identity(spec: IdentitySpec, lang: Language, seed: int) -> Identity:
    """Return a fully populated Identity for `lang`. Deterministic for a given seed."""
    rng = random.Random(seed)
    fake = Faker(lang.faker_locale)
    fake.seed_instance(seed)
    names = _Names(fake, lang, rng)
    code = lang.code

    manual = spec.model_dump(exclude={"mode"}, exclude_none=True) if spec.mode == "manual" else {}
    manual_address = manual.pop("address", {}) or {}

    gender = manual.get("gender") or rng.choice(["male", "female"])
    (given, given_latin), (family, family_latin) = names.given(gender), names.family()
    patronymic = None
    if code == "ru":
        patronymic = fake.middle_name_male() if gender == "male" else fake.middle_name_female()
        family = _ru_surname(family, gender)
        family_latin = anyascii(family)
    full = names.display(given, family, gender, patronymic)
    latin = f"{given_latin} {family_latin}".upper() if code not in _FAMILY_FIRST else \
        f"{family_latin} {given_latin}".upper()

    if "full_name" in manual and not ({"given_name", "family_name"} & manual.keys()):
        parts = manual["full_name"].split()
        given, family = parts[0], " ".join(parts[1:]) or parts[0]
    surname = manual.get("family_name", family)

    address = _random_address(fake, lang, rng).model_dump()
    address.update({k: v for k, v in manual_address.items() if v})

    father_given, _ = names.given("male")
    mother_given, _ = names.given("female")
    mother_family, _ = names.family()

    phone = f"+966 5{rng.randint(0, 9)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}" if code == "ar" \
        else fake.phone_number()
    email_user = f"{given_latin}.{family_latin}".lower().replace(" ", "").replace("'", "")
    generated = dict(
        full_name=full,
        given_name=given,
        family_name=family,
        latin_name=latin,
        gender=gender,
        date_of_birth=fake.date_of_birth(minimum_age=19, maximum_age=75),
        place_of_birth=address["city"],
        nationality=country_name(lang),
        phone=phone,
        email=f"{email_user}{rng.randint(1, 99)}@{rng.choice(['example.com', 'example.org', 'example.net'])}",
        id_number=f"1{rng.randint(10**8, 10**9 - 1)}" if code == "ar" else fake.ssn(),
        passport_number=fake.passport_number() if hasattr(fake, "passport_number") else
        f"{rng.choice(string.ascii_uppercase)}{rng.randint(10**7, 10**8 - 1)}",
        father_name=names.display(father_given, surname, "male"),
        mother_name=names.display(mother_given, surname if code == "ru" else mother_family, "female"),
        employer=f"شركة {rng.choice(_SA_STREETS)} للتجارة" if code == "ar" else fake.company(),
        job_title=rng.choice(_AR_JOBS) if code == "ar" else fake.job(),
        iban=_iban(_territory(lang), rng),
        account_number=_account_number(rng),
    )
    generated.update(manual)
    generated["address"] = Address(**address)
    if spec.mode == "manual" and "latin_name" not in manual and "full_name" in manual:
        generated["latin_name"] = anyascii(manual["full_name"]).upper()
    return Identity(**generated)


def identity_id(identity: Identity) -> str:
    return hashlib.sha1(identity.model_dump_json().encode()).hexdigest()[:12]


def age_on(identity: Identity, day: dt.date) -> int:
    dob = identity.date_of_birth
    return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))
