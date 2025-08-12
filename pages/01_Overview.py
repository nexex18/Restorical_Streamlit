import streamlit as st
from app_lib.db import query_df, db_exists
import plotly.express as px

st.set_page_config(page_title="Overview", page_icon="📈", layout="wide")


def metrics():
    df = query_df(
        """
        SELECT 
          (SELECT COUNT(*) FROM sites) AS total_sites,
          (SELECT COUNT(*) FROM site_summary WHERE has_narrative_content) AS sites_with_narratives,
          (SELECT COUNT(*) FROM site_summary WHERE has_documents) AS sites_with_documents,
          (SELECT COUNT(*) FROM site_qualification_results WHERE qualified) AS qualified_sites
        """
    )
    r = df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sites", f"{int(r.total_sites):,}")
    c2.metric("Sites w/ Narratives", f"{int(r.sites_with_narratives):,}")
    c3.metric("Sites w/ Documents", f"{int(r.sites_with_documents):,}")
    c4.metric("Qualified Sites", f"{int(r.qualified_sites):,}")


def tier_breakdown():
    df = query_df(
        """
        SELECT COALESCE(qualification_tier, 'UNSPECIFIED') AS tier,
               COUNT(*) AS count
        FROM site_qualification_results
        GROUP BY COALESCE(qualification_tier, 'UNSPECIFIED')
        ORDER BY count DESC
        """
    )
    fig = px.bar(df, x="tier", y="count", title="Qualification Tiers", text="count")
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)


def top_contaminants():
    df = query_df(
        """
        SELECT contaminant_type, COUNT(*) AS n
        FROM site_contaminants
        GROUP BY contaminant_type
        ORDER BY n DESC
        LIMIT 20
        """
    )
    fig = px.bar(df, x="n", y="contaminant_type", orientation="h", title="Top 20 Contaminants")
    st.plotly_chart(fig, use_container_width=True)


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Overview 📈")
    st.caption("High-level metrics and highlights across the dataset.")
    metrics()
    c1, c2 = st.columns([2, 1])
    with c1:
        tier_breakdown()
    with c2:
        st.subheader("Documents Summary")
        docs = query_df(
            "SELECT COUNT(*) AS documents, SUM(CASE WHEN download_status='success' THEN 1 ELSE 0 END) AS downloaded, SUM(CASE WHEN flagged_for_analysis THEN 1 ELSE 0 END) AS flagged FROM site_documents"
        ).iloc[0]
        st.metric("Documents", f"{int(docs.documents or 0):,}")
        st.metric("Downloaded", f"{int(docs.downloaded or 0):,}")
        st.metric("Flagged", f"{int(docs.flagged or 0):,}")

    st.subheader("Recent Site Overview")
    df = query_df(
        """
        SELECT site_id, site_name, site_address, total_documents, total_contaminants,
               has_documents, has_contaminants, scrape_status, status_icon
        FROM site_overview
        ORDER BY CAST(site_id AS INTEGER)
        LIMIT 500
        """
    )
    st.dataframe(df, use_container_width=True, height=500)


run()

