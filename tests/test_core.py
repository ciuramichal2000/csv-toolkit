import json
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from csvtool import core  # noqa: E402
from csvtool.__main__ import main  # noqa: E402


def test_decode_falls_back_to_windows_1250_for_polish_excel_files():
    raw = "imię;miasto\nŁukasz;Łódź\n".encode("cp1250")
    text, enc = core.decode(raw)
    assert enc == "cp1250" and "Łukasz" in text
    assert core.decode("﻿a,b\n".encode("utf-8"))[1] == "utf-8-sig"


@pytest.mark.parametrize("text,delim", [("a,b,c\n1,2,3\n", ","), ("a;b;c\n1;2;3\n", ";"), ("a\tb\n1\t2\n", "\t"),
                                        ('a;b\n"1,5";2\n"2,5";3\n', ";")])
def test_delimiter_is_detected_even_when_the_other_one_appears_inside_quotes(text, delim):
    assert core.sniff_delimiter(text) == delim


def test_parse_strips_blanks_and_ignores_extra_cells():
    rows = core.parse("name; city \n Ann ;Łódź\nBob;Kraków;extra\n")
    assert rows == [{"name": "Ann", "city": "Łódź"}, {"name": "Bob", "city": "Kraków"}]


def test_json_round_trip_keeps_unicode_and_column_order():
    rows = core.parse("id,name\n1,Łukasz\n2,Zoë\n")
    back = core.from_json(core.to_json(rows))
    assert back == "id,name\n1,Łukasz\n2,Zoë\n"
    with pytest.raises(ValueError):
        core.from_json('{"a": 1}')


@pytest.mark.parametrize("text,value", [("1 234,56", "1234.56"), ("1.234,56", "1234.56"), ("1,234.56", "1234.56"),
                                        ("-12.5", "-12.5"), ("7", "7"), (" 1 000", "1000")])
def test_numbers_in_polish_and_english_notation(text, value):
    assert core.parse_number(text) == Decimal(value)


def test_bad_numbers_and_dates_raise():
    with pytest.raises(ValueError):
        core.parse_number("12abc")
    with pytest.raises(ValueError):
        core.parse_date("31.02.2024")
    assert str(core.parse_date("14.05.2024")) == "2024-05-14"


SCHEMA = {"id": {"type": "int", "unique": True, "min": 1}, "amount": {"type": "number", "required": True, "max": 1000},
          "issued": {"type": "date"}, "code": {"pattern": "[A-Z]{2}-\\d{3}"}}


def test_validate_reports_each_problem_with_its_line_number():
    rows = core.parse("id,amount,issued,code\n1,10,2024-01-05,AB-123\n1,2000,31.02.2024,xx\n0,,2024-01-05,AB-1\n")
    msgs = [str(p) for p in core.validate(rows, SCHEMA)]
    assert "line 3, id: duplicate of line 2" in msgs
    assert any(m.startswith("line 3, amount: 2000") and "above the maximum" in m for m in msgs)
    assert any(m.startswith("line 3, issued: expected date") for m in msgs)
    assert any(m.startswith("line 3, code: 'xx' does not match") for m in msgs)
    assert "line 4, amount: required value is empty" in msgs
    assert any(m.startswith("line 4, id: 0 is below the minimum") for m in msgs)
    assert not [m for m in msgs if m.startswith("line 2")]


def test_missing_column_is_reported_once_on_the_header_line():
    problems = core.validate(core.parse("id\n1\n2\n"), {"id": {"type": "int"}, "amount": {"required": True}})
    assert [str(p) for p in problems] == ["line 1, amount: column is missing"]


def test_cli_validate_exit_code_and_output(tmp_path, capsys):
    f = tmp_path / "d.csv"
    f.write_text("id,amount\n1,5\n1,6\n", encoding="utf-8")
    s = tmp_path / "s.json"
    s.write_text(json.dumps({"id": {"type": "int", "unique": True}}), encoding="utf-8")
    assert main(["validate", str(f), "--schema", str(s)]) == 1
    assert "duplicate of line 2" in capsys.readouterr().out
    assert main(["to-json", str(f)]) == 0
