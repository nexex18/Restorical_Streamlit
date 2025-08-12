import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Narratives", page_icon="📜", layout="wide")


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Narratives 📜")
    st.caption("Browse site narratives by site and section.")

    site_options = query_df("SELECT DISTINCT site_id FROM site_narratives ORDER BY CAST(site_id AS INTEGER) LIMIT 10000")
    selected_site = st.selectbox("Select Site", site_options["site_id"].tolist()) if not site_options.empty else None

    if selected_site:
        df = query_df(
            """
            SELECT section_order, section_title, section_content, scraped_at
            FROM site_narratives
            WHERE site_id = ?
            ORDER BY section_order, scraped_at
            """,
            [selected_site],
        )

        if df.empty:
            st.info("No narrative sections for this site.")
        else:
            for _, row in df.iterrows():
                st.markdown(f"### {int(row.section_order)} — {row.section_title}")
                with st.expander("View content", expanded=False):
                    st.write(row.section_content)


run()

