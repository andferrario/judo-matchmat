from judo_matchmat.scoreboard import (
    TextBox,
    normalize_category,
    normalize_club,
    normalize_name,
    parse_board,
)


def box(text, x, y, score=0.99):
    return TextBox(text=text, score=score, x=x, y=y, height=20)


# Text as it comes out of OCR on a FIJLKAM scoreboard, shuffled on purpose.
BOARD = [
    box("0", 360, 75),
    box("L. BIANCHI", 10, 108),
    box("12RM2106-JUDO CLUB ROMA", 200, 75),
    box("-52 kg", 5, 40),
    box("4:00", 330, 40),
    box("M. ROSSI", 10, 76),
    box("Seniors - Female - Round of 16", 90, 41),
    box("08B01093-DojoEquipe", 200, 108),
    box("0", 360, 108),
]


def test_parse_board_reads_rows_by_position():
    r = parse_board(BOARD)
    assert r.category == "-52 kg"
    assert r.round == "Seniors - Female - Round of 16"
    assert (r.white.name, r.white.club) == ("M. ROSSI", "JUDO CLUB ROMA")
    assert (r.blue.name, r.blue.club) == ("L. BIANCHI", "DOJOEQUIPE")


def test_parse_board_without_round_keeps_athletes():
    boxes = [b for b in BOARD if "Round" not in b.text] + [box("Campionato Italiano Assoluto A2", 90, 41)]
    r = parse_board(boxes)
    assert r.round == ""
    assert r.white.name == "M. ROSSI"


def test_parse_board_ignores_low_confidence_and_incomplete():
    assert parse_board([box("M. ROSSI", 10, 76)]) is None
    noisy = BOARD + [box("xx", 10, 500, score=0.1)]
    assert parse_board(noisy).blue.name == "L. BIANCHI"


def test_normalizers():
    assert normalize_name("e.VERDI") == "E. VERDI"
    assert normalize_name("C.NERI") == normalize_name("C. NERI")
    assert normalize_club("19ME0266-PROVINCIALE") == "PROVINCIALE"
    assert normalize_club("JUDO ELBA") == "JUDO ELBA"
    assert normalize_club("01T03089-JUD0 ITALIA") == "JUDO ITALIA"
    assert normalize_club("D0JO SDK") == "DOJO SDK"
    assert normalize_club("SAV95JUD0") == "SAV95JUDO"
    assert normalize_club("IL RI0") == "IL RIO"
    assert normalize_club("CLUB 2000") == "CLUB 2000"
    assert normalize_category("52kg") == "-52 kg"
    assert normalize_category("+78 kg") == "+78 kg"
    assert normalize_category("Seniors") == ""
