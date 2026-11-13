"""The Memory's hanging rules (thorp.museum): an exhibit hangs in the era wing of its first year, in the country
wings of the countries that nominated it, and in the theme wings it names; the era wing past the cutoff is sealed."""

from thorp import museum

WINGS = [
    {"key": "au", "kind": "country", "country": "au", "year_from": None, "year_to": None, "sealed": False},
    {"key": "sail", "kind": "era", "country": "", "year_from": 1700, "year_to": 1849, "sealed": False},
    {"key": "engine", "kind": "era", "country": "", "year_from": 1850, "year_to": 1929, "sealed": False},
    {"key": "sealed", "kind": "era", "country": "", "year_from": 1930, "year_to": None, "sealed": True},
    {"key": "law", "kind": "theme", "country": "", "year_from": None, "year_to": None, "sealed": False},
]


def test_era_by_first_year():
    assert museum.era_of(1768, WINGS)["key"] == "sail"
    assert museum.era_of(1929, WINGS)["key"] == "engine"
    assert museum.era_of(1930, WINGS)["key"] == "sealed"
    assert museum.era_of(1200, WINGS) is None


def test_wings_of_an_exhibit():
    mabo = {"year_from": 1959, "countries": ["au"], "themes": ["law", "no-such-theme"]}
    assert museum.wings_of(mabo, WINGS) == ["sealed", "au", "law"]
    foreign = {"year_from": 1791, "countries": ["fr"], "themes": []}
    assert museum.wings_of(foreign, WINGS) == ["sail"]
