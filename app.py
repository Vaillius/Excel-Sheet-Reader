import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from pathlib import Path

# Fully offline — no external connections made anywhere in this app.

DB_PATH = os.path.join(Path.home(), "device_database", "devices.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Device Database",
    page_icon="🖥️",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        border: 1px solid #e9ecef;
    }
    .metric-label { font-size: 12px; color: #6c757d; margin-bottom: 4px; }
    .metric-value { font-size: 24px; font-weight: 600; color: #212529; }
    .success-box {
        background: #d1e7dd; border-radius: 6px;
        padding: 0.75rem 1rem; color: #0f5132; font-size: 14px;
    }
    .warning-box {
        background: #fff3cd; border-radius: 6px;
        padding: 0.75rem 1rem; color: #664d03; font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)


# ── Database helpers ────────────────────────────────────────────────────────────
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_readonly_conn():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)

def table_exists(conn, table="devices"):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None

def load_devices(conn) -> pd.DataFrame:
    if not table_exists(conn):
        return pd.DataFrame()
    return pd.read_sql("SELECT * FROM devices", conn)

def get_columns(conn):
    if not table_exists(conn):
        return []
    cur = conn.execute("PRAGMA table_info(devices)")
    return [row[1] for row in cur.fetchall()]

def import_dataframe(conn, df: pd.DataFrame):
    """Write dataframe to SQLite, replacing any existing data."""
    df.to_sql("devices", conn, if_exists="replace", index=False)
    conn.commit()

def run_sql(conn, query: str):
    try:
        return pd.read_sql(query, conn), None
    except Exception as e:
        return None, str(e)


# ── Sidebar nav ────────────────────────────────────────────────────────────────
conn = get_conn()
has_data = table_exists(conn)
record_count = int(pd.read_sql("SELECT COUNT(*) as n FROM devices", conn).iloc[0]["n"]) if has_data else 0

st.sidebar.title("🖥️ Device Database")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigation",
    ["📥  Import", "📋  Browse & Filter", "🔍  Query"],
    index=0,
)
st.sidebar.markdown("---")
if has_data:
    st.sidebar.markdown(f"**Records:** {record_count:,}")
    cols = get_columns(conn)
    st.sidebar.markdown(f"**Columns:** {len(cols)}")
    with st.sidebar.expander("Column list"):
        for c in cols:
            st.markdown(f"- `{c}`")
else:
    st.sidebar.info("No data imported yet.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — IMPORT
# ══════════════════════════════════════════════════════════════════════════════
if page == "📥  Import":
    st.title("📥 Import Excel / CSV")
    st.markdown("Upload a spreadsheet and it will be stored as a queryable SQLite database.")

    # ── Accepted column hints
    with st.expander("ℹ️  Expected columns (flexible — any extra columns are kept)"):
        st.markdown("""
| Column | Required | Notes |
|---|---|---|
| `device_id` | ✅ Yes | Unique identifier for each device |
| `campus` | Optional | Top-level location grouping |
| `building` | Optional | Building name or code |
| `floor` | Optional | Floor number / name |
| `room` | Optional | Room number / name |
| *any other columns* | Optional | Kept as-is (e.g. `type`, `status`, `ip_address`) |
""")

    uploaded = st.file_uploader(
        "Drop your file here",
        type=["xlsx", "xls", "csv"],
        help="Excel (.xlsx / .xls) or CSV files are supported.",
    )

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            else:
                df_raw = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        # Normalise column names
        df_raw.columns = [
            re.sub(r"\s+", "_", c.strip().lower()) for c in df_raw.columns
        ]
        df_raw = df_raw.fillna("").astype(str).apply(lambda col: col.str.strip())

        st.markdown("### Preview (first 10 rows)")
        st.dataframe(df_raw.head(10), use_container_width=True)

        # Validation
        if "device_id" not in df_raw.columns:
            st.error("❌  A `device_id` column is required. Please check your file.")
            st.stop()

        known = {"device_id", "campus", "building", "floor", "room"}
        extra = [c for c in df_raw.columns if c not in known]

        col1, col2, col3 = st.columns(3)
        col1.metric("Rows", f"{len(df_raw):,}")
        col2.metric("Columns", len(df_raw.columns))
        col3.metric("Extra columns", len(extra))

        if extra:
            st.info(f"Extra columns found and will be imported: **{', '.join(extra)}**")

        dupes = df_raw["device_id"].duplicated().sum()
        if dupes:
            st.warning(f"⚠️  {dupes} duplicate device_id value(s) detected. They will all be imported.")

        if st.button("✅  Import into database", type="primary"):
            import_dataframe(conn, df_raw)
            st.success(f"✅  {len(df_raw):,} records imported successfully!")
            st.balloons()
            st.rerun()

    elif has_data:
        st.markdown(
            f'<div class="success-box">✅ Database already contains <b>{record_count:,}</b> records. '
            f'Upload a new file to replace it.</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — BROWSE & FILTER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋  Browse & Filter":
    st.title("📋 Browse & Filter")

    if not has_data:
        st.warning("No data yet. Go to **Import** to load a spreadsheet.")
        st.stop()

    df = load_devices(conn)

    # ── Summary metrics
    loc_cols = [c for c in ["campus", "building", "floor", "room"] if c in df.columns]
    m_cols = st.columns(1 + len(loc_cols))
    m_cols[0].metric("Total devices", f"{len(df):,}")
    for i, lc in enumerate(loc_cols):
        m_cols[i + 1].metric(f"Unique {lc}s", df[lc].nunique())

    st.markdown("---")

    # ── Filters
    with st.expander("🔎  Filters", expanded=True):
        filter_cols = st.columns(min(len(loc_cols), 4)) if loc_cols else []
        filters = {}
        for i, lc in enumerate(loc_cols):
            options = sorted(df[lc].dropna().unique().tolist())
            options = [o for o in options if o != ""]
            sel = filter_cols[i].multiselect(lc.capitalize(), options, key=f"f_{lc}")
            if sel:
                filters[lc] = sel

        # Free text search
        search = st.text_input("🔍  Search across all columns", placeholder="e.g. LAP-001 or Server Room")

    # Apply filters
    filtered = df.copy()
    for col, vals in filters.items():
        filtered = filtered[filtered[col].isin(vals)]
    if search:
        mask = filtered.apply(
            lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1
        )
        filtered = filtered[mask]

    st.markdown(f"**{len(filtered):,}** record(s) shown")
    st.dataframe(filtered, use_container_width=True, height=480)

    # ── Download filtered results
    csv = filtered.to_csv(index=False).encode()
    st.download_button(
        "⬇️  Download filtered results as CSV",
        data=csv,
        file_name="filtered_devices.csv",
        mime="text/csv",
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — QUERY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍  Query":
    st.title("🔍 Query the Database")

    if not has_data:
        st.warning("No data yet. Go to **Import** to load a spreadsheet.")
        st.stop()

    cols = get_columns(conn)

    st.markdown("Write a `SELECT` query against the **`devices`** table.")
    st.code(f"-- Available columns: {', '.join(cols)}", language="sql")

    with st.expander("💡  Example queries"):
        examples = {
            "All devices (first 25)":             "SELECT * FROM devices LIMIT 25",
            "Count by campus":                    "SELECT campus, COUNT(*) as total FROM devices GROUP BY campus ORDER BY total DESC",
            "Count by building":                  "SELECT building, COUNT(*) as total FROM devices GROUP BY building ORDER BY total DESC",
            "Devices on a specific floor":        "SELECT * FROM devices WHERE floor = '3'",
            "Devices in a specific room":         "SELECT * FROM devices WHERE room = '101'",
            "Count by floor":                     "SELECT floor, COUNT(*) as total FROM devices GROUP BY floor ORDER BY total DESC",
            "Search by device ID":                "SELECT * FROM devices WHERE device_id LIKE '%LAP%'",
        }
        for label, query in examples.items():
            if st.button(label, key=f"ex_{label}"):
                st.session_state["sql_query"] = query

    default_sql = st.session_state.get("sql_query", "SELECT * FROM devices LIMIT 25")
    sql = st.text_area("SQL query", value=default_sql, height=120, key="sql_input")

    if st.button("▶  Run query", type="primary"):
        sql_upper = sql.strip().upper()
        blocked = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "ATTACH",
                   "DETACH", "PRAGMA", "SQLITE_MASTER", "SQLITE_TEMP_MASTER"]
        has_blocked = any(word in sql_upper for word in blocked)

        if not sql_upper.startswith("SELECT"):
            st.error("Only SELECT queries are allowed.")
        elif has_blocked:
            st.error("Query contains disallowed keywords.")
        else:
            try:
                ro_conn = get_readonly_conn()
                result_df, err = run_sql(ro_conn, sql)
            except Exception:
                result_df, err = run_sql(conn, sql)

            if err:
                st.error(f"SQL error: {err}")
            else:
                st.success(f"{len(result_df):,} row(s) returned")
                st.dataframe(result_df, use_container_width=True, height=400)
                csv = result_df.to_csv(index=False).encode()
                st.download_button("⬇️  Download results", csv, "sql_results.csv", "text/csv")
