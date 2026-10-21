"""python -m csvtool to-json in.csv > out.json | to-csv in.json | validate in.csv --schema schema.json"""
import argparse
import json
import sys

from . import core


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="csvtool")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("to-json").add_argument("path")
    sub.add_parser("to-csv").add_argument("path")
    v = sub.add_parser("validate")
    v.add_argument("path")
    v.add_argument("--schema", required=True)
    a = p.parse_args(argv)
    if a.cmd == "to-json":
        print(core.to_json(core.read_rows(a.path)))
        return 0
    if a.cmd == "to-csv":
        with open(a.path, encoding="utf-8") as f:
            sys.stdout.write(core.from_json(f.read()))
        return 0
    with open(a.schema, encoding="utf-8") as f:
        schema = json.load(f)
    problems = core.validate(core.read_rows(a.path), schema)
    for pr in problems:
        print(pr)
    print("%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
