"""Read messy CSV files, convert them to JSON and back, and validate them against a small schema."""
import csv
import datetime as dt
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple


def decode(raw: bytes) -> Tuple[str, str]:
    """UTF-8 (with or without BOM) first, then Windows-1250, which is what Polish Excel exports use."""
    for enc in ("utf-8-sig", "cp1250"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def sniff_delimiter(text: str) -> str:
    """Pick the delimiter that gives the most consistent column count over the first lines."""
    lines = [l for l in text.splitlines()[:20] if l.strip()]
    best, best_score = ",", -1.0
    for d in (",", ";", "\t", "|"):
        counts = [len(next(csv.reader([l], delimiter=d))) for l in lines]
        if not counts or counts[0] < 2:
            continue
        consistent = sum(1 for c in counts if c == counts[0]) / len(counts)
        score = consistent * 10 + counts[0] / 100
        if score > best_score:
            best, best_score = d, score
    return best


def read_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "rb") as f:
        text, _ = decode(f.read())
    return parse(text)


def parse(text: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=sniff_delimiter(text))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None} for row in reader]


def to_json(rows: List[Dict[str, str]]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


def from_json(text: str) -> str:
    rows = json.loads(text)
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError("expected a JSON array of objects")
    columns: List[str] = []
    for r in rows:
        for k in r:
            if k not in columns:
                columns.append(k)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def parse_number(value: str) -> Decimal:
    """'1 234,56', '1.234,56', '1,234.56' and '-12.5' all read as numbers; ambiguous input raises."""
    s = re.sub(r"[\s ]", "", value)
    if not s:
        raise ValueError("empty")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError("not a number: %r" % value)


def parse_date(value: str) -> dt.date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("not a date: %r" % value)


@dataclass
class Problem:
    line: int          # line number in the file (header = line 1)
    column: str
    message: str

    def __str__(self):
        return "line %d, %s: %s" % (self.line, self.column, self.message)


def validate(rows: List[Dict[str, str]], schema: Dict[str, Dict[str, object]]) -> List[Problem]:
    """schema: {column: {"type": "int|number|date|text", "required": bool, "pattern": regex, "min": n, "max": n, "unique": bool}}"""
    problems: List[Problem] = []
    seen: Dict[str, Dict[str, int]] = {c: {} for c, r in schema.items() if r.get("unique")}
    for i, row in enumerate(rows, start=2):
        for col, rule in schema.items():
            if col not in row:
                if i == 2:
                    problems.append(Problem(1, col, "column is missing"))
                continue
            val = row[col]
            if val == "":
                if rule.get("required"):
                    problems.append(Problem(i, col, "required value is empty"))
                continue
            try:
                kind = rule.get("type", "text")
                if kind == "int":
                    n: Optional[Decimal] = Decimal(int(val))
                elif kind == "number":
                    n = parse_number(val)
                elif kind == "date":
                    parse_date(val)
                    n = None
                else:
                    n = None
                if n is not None:
                    if "min" in rule and n < Decimal(str(rule["min"])):
                        problems.append(Problem(i, col, "%s is below the minimum %s" % (val, rule["min"])))
                    if "max" in rule and n > Decimal(str(rule["max"])):
                        problems.append(Problem(i, col, "%s is above the maximum %s" % (val, rule["max"])))
            except ValueError as e:
                problems.append(Problem(i, col, "expected %s (%s)" % (rule.get("type"), e)))
                continue
            if rule.get("pattern") and not re.fullmatch(str(rule["pattern"]), val):
                problems.append(Problem(i, col, "%r does not match %s" % (val, rule["pattern"])))
            if rule.get("unique"):
                if val in seen[col]:
                    problems.append(Problem(i, col, "duplicate of line %d" % seen[col][val]))
                else:
                    seen[col][val] = i
    return problems
