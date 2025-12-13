import streamlit as st
import plotly.express as px
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Contaminants", page_icon="🧪", layout="wide")


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Contaminants 🧪")
    st.caption("Top contaminant types and per-site details.")

    # Top contaminants
    top = query_df(
        """
        SELECT contaminant_type, COUNT(*) AS n
        FROM site_contaminants
        GROUP BY contaminant_type
        ORDER BY n DESC
        LIMIT 30
        """
    )
    fig = px.bar(top, x="n", y="contaminant_type", orientation="h", title="Top Contaminant Types")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Per-site contaminants")
    site_id = st.text_input("Filter by Site ID (optional)", "")
    where = "WHERE site_id = ?" if site_id else ""
    params = [site_id] if site_id else []
    df = query_df(
        f"""
        SELECT site_id, contaminant_type, soil_status, groundwater_status, surface_water_status, air_status, sediment_status, bedrock_status
        FROM site_contaminants
        {where}
        ORDER BY site_id, contaminant_type
        LIMIT 10000
        """,
        params,
    )
    st.dataframe(df, use_container_width=True, height=600)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="contaminants_export.csv",
        mime="text/csv",
    )


run()

