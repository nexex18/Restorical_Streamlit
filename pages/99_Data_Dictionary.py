import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Data Dictionary", page_icon="📚", layout="wide")


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Data Dictionary 📚")
    st.caption("Inspect tables and views, columns and sample rows.")

    tables = query_df(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
        ORDER BY type DESC, name ASC
        """
    )
    choice = st.selectbox("Select a table/view", tables["name"].tolist()) if not tables.empty else None

    if choice:
        cols = query_df(
            """
            PRAGMA table_info(%s)
            """ % choice
        )
        st.subheader("Columns")
        st.dataframe(cols, use_container_width=True)

        st.subheader("Sample Rows")
        df = query_df(f"SELECT * FROM {choice} LIMIT 100")
        st.dataframe(df, use_container_width=True, height=500)


run()

