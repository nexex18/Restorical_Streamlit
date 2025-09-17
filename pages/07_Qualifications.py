import streamlit as st
import plotly.express as px
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Qualifications", page_icon="✅", layout="wide")


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Qualifications ✅")
    st.caption("Analyze qualification outcomes, tiers, and confidence scores.")

    # Filters
    tiers = query_df("SELECT DISTINCT COALESCE(qualification_tier,'UNSPECIFIED') AS t FROM site_qualification_results ORDER BY t")
    tier_sel = st.multiselect("Tier", tiers["t"].tolist(), [])
    qual_sel = st.selectbox("Qualified?", ["Any", "Yes", "No"], index=0)

    where, params = [], []
    if tier_sel:
        where.append("COALESCE(qualification_tier,'UNSPECIFIED') IN (%s)" % (",".join(["?"]*len(tier_sel))))
        params += tier_sel
    if qual_sel != "Any":
        where.append("qualified = ?")
        params.append(1 if qual_sel == "Yes" else 0)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    df = query_df(
        f"""
        SELECT id, site_id, qualified, qualification_tier, confidence_score, 
               document_type_analyzed, document_quality_score, analyzed_at
        FROM site_qualification_results
        {where_sql}
        ORDER BY analyzed_at DESC
        LIMIT 10000
        """,
        params,
    )

    # Charts
    agg = query_df(
        f"""
        SELECT COALESCE(qualification_tier,'UNSPECIFIED') AS tier, COUNT(*) AS n
        FROM site_qualification_results
        {where_sql}
        GROUP BY COALESCE(qualification_tier,'UNSPECIFIED')
        ORDER BY n DESC
        """,
        params,
    )
    col1, col2 = st.columns([1,1])
    with col1:
        if not agg.empty:
            fig = px.bar(agg, x="tier", y="n", title="Count by Tier", text="n")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not df.empty:
            fig2 = px.histogram(df, x="confidence_score", nbins=30, title="Confidence Score Distribution")
            st.plotly_chart(fig2, use_container_width=True)

    st.write(f"Results: {len(df):,}")
    st.dataframe(df, use_container_width=True, height=600)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="qualifications_export.csv",
        mime="text/csv",
    )


run()

