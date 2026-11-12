"""The tests table's source (thorp.viable.s4_intelligence.tests_store): every fleet test has a row, with
its chain and rung, and the catalogue is not empty."""

from thorp.viable.s4_intelligence import tests_store


def test_every_fleet_test_has_a_row() -> None:
    rows = tests_store.desired()
    assert len(rows) >= 20
    assert {r["key"] for r in rows} == set(__import__("thorp.fleet", fromlist=["TRICKS"]).TRICKS)
    assert all(r["name"] for r in rows)


def test_the_chain_tests_carry_their_chain_and_rung() -> None:
    rows = {r["key"]: r for r in tests_store.desired()}
    assert rows["kin_test"]["chain"] == "origin_test"
    assert rows["kin_test"]["rung"]
    assert rows["logic_test"]["chain"] == ""
