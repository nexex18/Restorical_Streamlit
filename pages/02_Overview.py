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
    
    # Initialize pagination state
    if 'overview_page' not in st.session_state:
        st.session_state.overview_page = 1
    
    # Get total count of sites
    total_count = int(query_df("SELECT COUNT(*) as count FROM site_overview").iloc[0]['count'])
    items_per_page = 500
    total_pages = int((total_count + items_per_page - 1) // items_per_page)  # Ceiling division, ensure int
    
    # Calculate offset for current page
    offset = (st.session_state.overview_page - 1) * items_per_page
    
    # Query with pagination
    df = query_df(
        f"""
        SELECT site_id, site_name, site_address, total_documents, total_contaminants,
               has_documents, has_contaminants, scrape_status, status_icon
        FROM site_overview
        ORDER BY CAST(site_id AS INTEGER)
        LIMIT {items_per_page}
        OFFSET {offset}
        """
    )
    
    # Pagination controls and download button
    if total_pages > 1:
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        
        with col1:
            if st.button("← Previous", disabled=(st.session_state.overview_page == 1)):
                st.session_state.overview_page -= 1
                st.rerun()
        
        with col2:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.overview_page} of {total_pages} (Total sites: {total_count:,})</div>", unsafe_allow_html=True)
        
        with col3:
            if st.button("Next →", disabled=(st.session_state.overview_page >= total_pages)):
                st.session_state.overview_page += 1
                st.rerun()
        
        with col4:
            # Add download all button
            if st.button("📥 Download All", key="overview_download_all"):
                with st.spinner(f"Preparing download of all {total_count:,} sites..."):
                    # Query ALL data without pagination
                    all_df = query_df(
                        """
                        SELECT site_id, site_name, site_address, total_documents, total_contaminants,
                               has_documents, has_contaminants, scrape_status, status_icon
                        FROM site_overview
                        ORDER BY CAST(site_id AS INTEGER)
                        """
                    )
                    
                    # Convert to CSV
                    csv = all_df.to_csv(index=False)
                    
                    # Offer download
                    st.download_button(
                        label="💾 Click to save CSV",
                        data=csv,
                        file_name="all_sites_overview.csv",
                        mime="text/csv",
                        key="overview_download_csv"
                    )
    else:
        # If only one page, still show download button for consistency
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("📥 Download All", key="overview_download_single"):
                # Convert current df to CSV (since it's all the data anyway)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="💾 Click to save CSV",
                    data=csv,
                    file_name="all_sites_overview.csv",
                    mime="text/csv",
                    key="overview_download_csv_single"
                )
    
    # Display dataframe
    st.dataframe(df, use_container_width=True, height=500)


run()

