import re
import unicodedata

from config.constants import DEFAULT_STATE
from config.districts import TN_DISTRICTS

# Current Tamil Nadu district names, including common legacy spellings used by
# tourism datasets. Values are canonical names used by the application.
TN_DISTRICT_ALIASES = {
    "ariyalur": "Ariyalur",
    "chengalpattu": "Chengalpattu",
    "chennai": "Chennai",
    "coimbatore": "Coimbatore",
    "cuddalore": "Cuddalore",
    "dharmapuri": "Dharmapuri",
    "dindigul": "Dindigul",
    "erode": "Erode",
    "kallakurichi": "Kallakurichi",
    "kancheepuram": "Kancheepuram",
    "kanchipuram": "Kancheepuram",
    "karur": "Karur",
    "krishnagiri": "Krishnagiri",
    "madurai": "Madurai",
    "mayiladuthurai": "Mayiladuthurai",
    "kanyakumari": "Kanyakumari",
    "kanniyakumari": "Kanyakumari",
    "nagapattinam": "Nagapattinam",
    "namakkal": "Namakkal",
    "perambalur": "Perambalur",
    "pudukkottai": "Pudukkottai",
    "ramanathapuram": "Ramanathapuram",
    "ranipet": "Ranipet",
    "salem": "Salem",
    "sivaganga": "Sivaganga",
    "sivagangai": "Sivaganga",
    "tenkasi": "Tenkasi",
    "thanjavur": "Thanjavur",
    "theni": "Theni",
    "the nilgiris": "Nilgiris",
    "nilgiris": "Nilgiris",
    "tiruchirappalli": "Tiruchirappalli",
    "tiruchirapalli": "Tiruchirappalli",
    "trichy": "Tiruchirappalli",
    "tirunelveli": "Tirunelveli",
    "tirupathur": "Tirupathur",
    "tiruppur": "Tiruppur",
    "tiruvallur": "Tiruvallur",
    "thiruvallur": "Tiruvallur",
    "tiruvannamalai": "Tiruvannamalai",
    "thiruvannamalai": "Tiruvannamalai",
    "tiruvarur": "Tiruvarur",
    "thiruvarur": "Tiruvarur",
    "thoothukudi": "Thoothukudi",
    "tuticorin": "Thoothukudi",
    "vellore": "Vellore",
    "viluppuram": "Viluppuram",
    "villupuram": "Viluppuram",
    "virudhunagar": "Virudhunagar",
    # Spellings used by OpenStreetMap, Wikidata and government portals.
    "chengalpet": "Chengalpattu",
    "chengalpettu": "Chengalpattu",
    "kanchipuram": "Kancheepuram",
    "kanniakumari": "Kanyakumari",
    "the nilgris": "Nilgiris",
    "nilgris": "Nilgiris",
    "tirupattur": "Tirupathur",
    "thirupattur": "Tirupathur",
    "thirupathur": "Tirupathur",
    "tiruvallur": "Tiruvallur",
    "trichirappalli": "Tiruchirappalli",
    "tiruchi": "Tiruchirappalli",
    "thiruchirappalli": "Tiruchirappalli",
    "thirunelveli": "Tirunelveli",
    "thiruppur": "Tiruppur",
    "tirupur": "Tiruppur",
    "thoothukkudi": "Thoothukudi",
    "villupuram": "Viluppuram",
    "vilupuram": "Viluppuram",
    "kallakurichchi": "Kallakurichi",
    "pudukottai": "Pudukkottai",
    "ramnad": "Ramanathapuram",
    "dindugal": "Dindigul",
    "kanyakumari district": "Kanyakumari",
}

VALID_TN_DISTRICTS = frozenset(TN_DISTRICTS)

_DISTRICT_SUFFIX_RE = re.compile(r"\s+(district|dt\.?|dist\.?)$", re.IGNORECASE)


def resolve_district(value):
    """Map free text such as "Sivagangai district" or "The Nilgris" to a
    canonical district name, or return None when it is not a TN district.

    Exact aliases are tried first; a conservative fuzzy match then absorbs
    the one-letter typos that government pages regularly contain.
    """
    if value is None:
        return None
    text = " ".join(str(value).replace(" ", " ").split()).strip(" ,.-")
    if not text:
        return None
    candidates = [text, _DISTRICT_SUFFIX_RE.sub("", text)]
    if candidates[-1].casefold().startswith("the "):
        candidates.append(candidates[-1][4:])
    for candidate in candidates:
        canonical = TN_DISTRICT_ALIASES.get(candidate.casefold())
        if canonical:
            return canonical
        if candidate in VALID_TN_DISTRICTS:
            return candidate
    import difflib
    match = difflib.get_close_matches(candidates[-1].casefold(), TN_DISTRICT_ALIASES.keys(), n=1, cutoff=0.88)
    return TN_DISTRICT_ALIASES[match[0]] if match else None

EDUCATION_PATTERNS = (
    r"\bschool\b",
    r"\bcollege\b",
    r"\buniversity\b",
    r"\binstitute\b",
    r"\bacademy\b",
    r"\bpolytechnic\b",
    r"\bcampus\b",
    r"\bvidyalaya\b",
    r"\bmatriculation\b",
    r"\bhigher secondary\b",
    r"\bengineering college\b",
    r"\bmedical college\b",
    r"\biit\b",
    r"\bnit\b",
    r"\biim\b",
    r"\bskct\b",
    r"\btpgit\b",
    r"\bfront gate\b",
    r"\bmain gate\b",
    r"\bback gate\b",
    r"educational institution",
)

INVALID_TOURISM_PATTERNS = (
    # Commercial / Industrial / Health / Retail
    r"\b(boteling plant|bottling plant|biogas plant)\b",
    r"\b(showroom|outlet)\b",
    r"\b(chicken 65 shop|fast food|tea stall)\b",
    r"\b(bharat scans|scan centre|scan center|diagnostic centre|diagnostic center)\b",
    r"\b(herbal mills|binny mills building)\b",
    r"\b(dugar group of company)\b",
    r"\b(thirumana mandabam|kalyana mandapam)\b",
    r"\b(home finders estate)\b",
    # Administrative / Offices
    r"\b(mla office|egp office|my office)\b",
    # Residential / Personal accommodations / Slang
    r"\b(lake flats|sangeetha hostel|abandoned house|forest quarters|bhooth banglou)\b",
    r"\b(manjula house|pamayan organic form house|dream house|ramu veedu)\b",
    r"\b(my room|anna room)\b",
    # Roads / Traffic / Signage / Utilities / Local grounds
    r"\b(road to b|s bend)\b",
    r"\b(military road roundabout|thiruvagoundanur roundabout|avr roundabout)\b",
    r"\b(namma tambaram|southernmost post box)\b",
    r"\b(melakkadu mayanam|thingal sandhai)\b",
    # Specific personal nonsense tags
    r"\b(sriram\.s|ganesan ayya|surrapati)\b",
)

OUT_OF_STATE_DESTINATIONS = frozenset({
    "bandipur national park",
    "bannerghatta national park",
})

# Known legitimate heritage sites / historical gates / museums to never filter out
VALID_HERITAGE_EXCEPTIONS = frozenset({
    "delhi gate", "st. thomas gate", "wallajah gate", "st. george's gate", "north gate", "pully gate", "town gate",
    "police museum", "tamil nadu police museum", "tamilnadu police museum", "chennai railway museum",
    "vivekananda house and museum", "kamaraj memorial house", "kamarajar's house", "stone house",
    "chettinad house", "ziegenbalg house", "house of kalam (apj abdul kalam house/museum)", "gnanananda house",
    "annamalai raja's waiting house", "chettiars houses", "vrvm chettiars house", "hindu house", "syrian christian house",
    "lake boat house", "ttdc boat house", "muttukadu boat house", "boathouse", "pichavaram boathouse",
    "mathoor hanging bridge", "mathur hanging aqueduct", "pamban bridge", "ram sethu bridge",
    "tea museum / tea factory", "crocodile bank", "pondy bazaar", "the nilgiri mountain railway",
})


def canonicalize_district(value):
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    return resolve_district(text) or TN_DISTRICT_ALIASES.get(text.casefold(), text)


# Districts created by splitting another (1990s-2020) and Chennai's growth
# into its neighbours. Sources still file many places under the old
# district, so the same destination can arrive under either name.
DISTRICT_SPLITS = (
    ("Kancheepuram", "Chengalpattu"), ("Tirunelveli", "Tenkasi"), ("Vellore", "Ranipet"),
    ("Vellore", "Tirupathur"), ("Viluppuram", "Kallakurichi"), ("Nagapattinam", "Mayiladuthurai"),
    ("Dharmapuri", "Krishnagiri"), ("Coimbatore", "Tiruppur"), ("Erode", "Tiruppur"),
    ("Perambalur", "Ariyalur"), ("Thanjavur", "Tiruvarur"), ("Nagapattinam", "Tiruvarur"),
    ("Chennai", "Kancheepuram"), ("Chennai", "Tiruvallur"), ("Chennai", "Chengalpattu"),
    ("Madurai", "Theni"), ("Ramanathapuram", "Sivaganga"), ("Ramanathapuram", "Virudhunagar"),
    ("Tiruchirappalli", "Karur"), ("Tirunelveli", "Thoothukudi"), ("Salem", "Namakkal"),
)
RELATED_DISTRICTS = {}
for _old, _new in DISTRICT_SPLITS:
    RELATED_DISTRICTS.setdefault(_old, []).append(_new)
    RELATED_DISTRICTS.setdefault(_new, []).append(_old)


def is_tamil_nadu_district(value):
    district = canonicalize_district(value)
    return district in VALID_TN_DISTRICTS


def is_educational_place(place):
    fields = (
        place.get("place_name"),
        place.get("category_name"),
        place.get("subcategory"),
        place.get("description"),
        place.get("amenity"),
        place.get("tourism"),
    )
    text = " ".join(str(value or "") for value in fields).casefold()
    return any(re.search(pattern, text) for pattern in EDUCATION_PATTERNS)


def is_invalid_tourism_place(place):
    name = str(place.get("place_name") or "").strip().casefold()
    if name in VALID_HERITAGE_EXCEPTIONS:
        return False
    if name in OUT_OF_STATE_DESTINATIONS:
        return True
    if is_educational_place(place):
        return True
    fields = (
        place.get("place_name"),
        place.get("category_name"),
        place.get("subcategory"),
        place.get("description"),
        place.get("amenity"),
        place.get("tourism"),
    )
    text = " ".join(str(value or "") for value in fields).casefold()
    return any(re.search(pattern, text) for pattern in INVALID_TOURISM_PATTERNS)


def filter_tourism_records(records):
    if records is None:
        return records
    result = []
    for record in records:
        item = dict(record)
        item["district"] = canonicalize_district(item.get("district"))
        if not is_tamil_nadu_district(item.get("district")):
            continue
        if is_invalid_tourism_place(item):
            continue
        item["state"] = DEFAULT_STATE
        result.append(item)
    return result


def name_key(name):
    """Normalised identity of a destination name used for cross-source merging.

    "Sri Meenakshi Amman Temple" and "Meenakshi Amman Temple." share a key;
    different localities ("X Temple, Hosur" vs "X Temple, Arani") do not.
    """
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t not in {"arulmigu", "sri", "shri", "shree", "the", "thiru", "a"}]
    return " ".join(tokens)
