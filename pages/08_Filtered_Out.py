import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Filtered-Out Sites", page_icon="📝", layout="wide")


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Filtered-Out Sites 📝")
    st.caption("Sites excluded from Prospecting due to Tribal relation or Do-Not-Contact policy.")

    q = st.text_input("Search (site id, name, address)", "")
    like = f"%{q}%" if q else None

    tabs = st.tabs(["Tribal-Related", "Do Not Contact"])

    with tabs[0]:
        df = query_df(
            """
            SELECT DISTINCT s.site_id, s.site_name, s.site_address
            FROM site_overview s
            WHERE s.site_id IN (
              SELECT site_id FROM site_qualification_results WHERE COALESCE(tribal_site,0)=1
            )
            ORDER BY CAST(s.site_id AS INTEGER)
            LIMIT 10000
            """
        )
        if q:
            df = df[(df["site_id"].astype(str).str.contains(q, case=False, na=False)) |
                    (df["site_name"].fillna("").str.contains(q, case=False)) |
                    (df["site_address"].fillna("").str.contains(q, case=False))]
        st.write(f"Rows: {len(df):,}")
        st.dataframe(df, use_container_width=True, height=500)
        if not df.empty:
            st.download_button("Download CSV (Tribal)", df.to_csv(index=False).encode("utf-8"), "filtered_tribal.csv", "text/csv")

    with tabs[1]:
        df2 = query_df(
            """
            SELECT DISTINCT s.site_id, s.site_name, s.site_address, d.organization_name AS matched_org
            FROM site_overview s
            JOIN "Do_Not_Contact_Sites" d
              ON UPPER(TRIM(COALESCE(s.site_name,''))) = UPPER(TRIM(COALESCE(d.organization_name,'')))
              OR UPPER(TRIM(COALESCE(s.site_address,''))) = UPPER(TRIM(COALESCE(d.site_address,'')))
            WHERE COALESCE(d.active,1)=1
            ORDER BY CAST(s.site_id AS INTEGER)
            LIMIT 10000
            """
        )
        if q:
            df2 = df2[(df2["site_id"].astype(str).str.contains(q, case=False, na=False)) |
                      (df2["site_name"].fillna("").str.contains(q, case=False)) |
                      (df2["site_address"].fillna("").str.contains(q, case=False)) |
                      (df2["matched_org"].fillna("").str.contains(q, case=False))]
        st.write(f"Rows: {len(df2):,}")
        st.dataframe(df2, use_container_width=True, height=500)
        if not df2.empty:
            st.download_button("Download CSV (DNC)", df2.to_csv(index=False).encode("utf-8"), "filtered_dnc.csv", "text/csv")


run()

