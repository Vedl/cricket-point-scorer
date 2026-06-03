from platform_core.csv_import import parse_squad_csv


def test_pool_format():
    text = "Player,Role,Team,BasePrice\nLionel Messi,FWD,Argentina,0\nKylian Mbappe,FWD,France,5\n"
    r = parse_squad_csv(text)
    assert r.kind == "pool"
    assert r.ok
    assert [p.name for p in r.players] == ["Lionel Messi", "Kylian Mbappe"]
    assert r.players[1].base_price == 5


def test_pool_position_and_country_aliases():
    text = "Player,Position,Country\nManuel Neuer,GK,Germany\n"
    r = parse_squad_csv(text)
    assert r.ok and r.players[0].role == "GK" and r.players[0].team == "Germany"


def test_roster_format():
    text = (
        "Participant,Player,Role,Team,Price\n"
        "Smudge49,Jos Buttler,WK-Batsman,England,60\n"
        "Smudge49,Harry Brook,Batsman,England,70\n"
    )
    r = parse_squad_csv(text)
    assert r.kind == "roster" and r.ok
    assert len(r.assignments) == 2
    assert r.assignments[0].price == 60


def test_bom_is_stripped():
    text = "﻿Participant,Player,Price\nA,X,10\n"
    r = parse_squad_csv(text)
    assert r.kind == "roster" and r.ok


def test_bad_price_is_an_error():
    text = "Player,Price\nMessi,abc\n"
    r = parse_squad_csv(text)
    assert not r.ok
    assert any("not a number" in e for e in r.errors)


def test_duplicate_player_warns_pool():
    text = "Player\nMessi\nMessi\n"
    r = parse_squad_csv(text)
    assert r.ok
    assert len(r.players) == 1
    assert any("duplicate" in w for w in r.warnings)


def test_missing_columns_error():
    text = "Foo,Bar\n1,2\n"
    r = parse_squad_csv(text)
    assert not r.ok
    assert any("Header must contain" in e for e in r.errors)


def test_empty_file():
    assert not parse_squad_csv("").ok


def test_roster_missing_participant_row_error():
    text = "Participant,Player\n,Messi\n"
    r = parse_squad_csv(text)
    assert any("missing participant" in e for e in r.errors)
