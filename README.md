# csv-toolkit

Reads the CSV files that real people send: Polish Excel exports in Windows-1250, semicolon or tab separated, numbers like `1 234,56`, dates like `14.05.2024`. Converts them to JSON and back, and validates them against a small schema (type, required, min/max, regex, unique), reporting **every** problem with its line number instead of stopping at the first.

```
python -m csvtool to-json invoices.csv
python -m csvtool validate invoices.csv --schema schema.json
python -m pytest
```

Pure Python standard library; money is read as `Decimal`, never `float`. Built with AI coding assistance; tests cover encodings, delimiters, number and date notations, the validator and the command line.
