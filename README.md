# Device Database App

A Streamlit app that imports an Excel/CSV spreadsheet into a SQLite database and lets you browse, filter, and query it — including natural-language questions powered by Claude AI.

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

The app opens at http://localhost:8501

## Features

| Tab | What it does |
|---|---|
| **Import** | Upload `.xlsx`, `.xls`, or `.csv`; data is stored in `devices.db` |
| **Browse & Filter** | Multiselect filters for campus / building / floor / room + free-text search ||
| **Query → Raw SQL** | Write any `SELECT` against the `devices` table |

## Spreadsheet format

Any column names are accepted.
Column names are normalised automatically (spaces → underscores, lowercased).

## Notes

- The natural-language query tab calls the Anthropic API — make sure your network allows outbound HTTPS to `api.anthropic.com`.
- The SQLite database (`devices.db`) is created in the same directory as `app.py`. Re-importing replaces all existing data.
- Only `SELECT` queries are permitted in the Raw SQL tab.
