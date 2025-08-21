import os
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import time

from app_lib.db import query_df, db_exists, DB_PATH

st.set_page_config(page_title="Eco Site Analytics", page_icon="📊", layout="wide")

# URL prefix for deployment behind nginx (e.g., '/streamlit')
URL_PREFIX = os.environ.get('URL_PREFIX', '')

# Authentication
def check_auth():
    """Check if user is authenticated"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        # Show login form
        st.title("🔐 Authentication Required")
        st.markdown("Please enter the password to access Eco Site Analytics.")
        
        with st.form("login_form"):
            password = st.text_input("Password", type="password", key="password_input")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                # Check password against environment variable or default
                AUTH_TOKEN = os.environ.get('AUTH_TOKEN', 'secret123')
                if password == AUTH_TOKEN:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Invalid password. Please try again.")
        
        # Stop execution if not authenticated
        st.stop()
    
    # Add logout button in sidebar if authenticated
    with st.sidebar:
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()


def build_site_filters_ui():
    """Render site-level filters and return SQL where + params for site_overview."""
    
    # Create an expander for filters to save space
    with st.expander("🔍 Filters", expanded=True):
        # Create two main columns - wider left for other filters, narrower right for qualification filters
        left_col, right_col = st.columns([3, 1])
        
        # Left column - All other filters
        with left_col:
            # Search bar at the top
            q = st.text_input("Search (name, address, site_id)", "", key="search_input")
            
            # Document and narrative filters
            c1, c2 = st.columns(2)
            with c1:
                has_docs = st.selectbox("Has Docs", ["Any", "Yes", "No"], index=0, key="has_docs_select")
            with c2:
                has_narr = st.selectbox("Has Narrative", ["Any", "Yes", "No"], index=0, key="has_narr_select")
            
            # Contamination medium filters
            medium_to_col = {
                "Groundwater": "groundwater_status",
                "Surface Water": "surface_water_status",
                "Air": "air_status",
                "Sediment": "sediment_status",
                "Bedrock": "bedrock_status",
            }
            media_labels = list(medium_to_col.keys())
            c3, c4 = st.columns(2)
            with c3:
                medium_sel = st.multiselect("Contamination Medium", options=media_labels, default=[], key="medium_select")
            # Build status options from selected media (or all if none selected)
            sel_cols = [medium_to_col[m] for m in medium_sel] if medium_sel else list(medium_to_col.values())
            union_sql = " UNION ".join([f"SELECT {c} AS s FROM site_contaminants" for c in sel_cols])
            status_opts_df = query_df(
                f"SELECT DISTINCT s AS status FROM ({union_sql}) t WHERE s IS NOT NULL AND TRIM(s) <> '' ORDER BY status"
            )
            status_opts = status_opts_df["status"].tolist()
            with c4:
                medium_status_sel = st.multiselect("Medium Status", options=status_opts, default=[], key="status_select")
            
            # Global stats for numeric sliders from site_summary
            stats = query_df(
                """
                SELECT 
                  MIN(COALESCE(total_narrative_sections,0)) AS narr_min,
                  MAX(COALESCE(total_narrative_sections,0)) AS narr_max,
                  MIN(COALESCE(total_documents,0)) AS docs_min,
                  MAX(COALESCE(total_documents,0)) AS docs_max,
                  MIN(COALESCE(document_date_range_years,0)) AS span_min,
                  MAX(COALESCE(document_date_range_years,0)) AS span_max
                FROM site_summary
                """
            )
            if stats.empty:
                narr_min = narr_max = 0
                docs_min = docs_max = 0
                span_min = span_max = 0
            else:
                r = stats.iloc[0]
                narr_min, narr_max = int(r.narr_min or 0), int(r.narr_max or 0)
                docs_min, docs_max = int(r.docs_min or 0), int(r.docs_max or 0)
                span_min, span_max = int(r.span_min or 0), int(r.span_max or 0)
            
            # Numeric sliders
            n1, n2, n3 = st.columns(3)
            # Ensure sliders have a valid range even when min==max
            narr_max_eff = narr_max if narr_max > narr_min else narr_min + 1
            docs_max_eff = docs_max if docs_max > docs_min else docs_min + 1
            span_max_eff = span_max if span_max > span_min else span_min + 1
            
            with n1:
                narr_range = st.slider(
                    "Narratives",
                    min_value=narr_min,
                    max_value=narr_max_eff,
                    value=(narr_min, narr_max if narr_max > narr_min else narr_min + 1),
                    key="narr_slider"
                )
            with n2:
                docs_range = st.slider(
                    "Documents",
                    min_value=docs_min,
                    max_value=docs_max_eff,
                    value=(docs_min, docs_max if docs_max > docs_min else docs_min + 1),
                    key="docs_slider"
                )
            with n3:
                span_range = st.slider(
                    "Year Span",
                    min_value=span_min,
                    max_value=span_max_eff,
                    value=(span_min, span_max if span_max > span_min else span_min + 1),
                    key="span_slider"
                )
        
        # Right column - Qualification-related filters
        with right_col:
            processed_filter = st.selectbox("Processed for qualification", ["All", "Yes", "No"], index=0, key="processed_select")
            
            # Qualification Tier
            tiers_df = query_df("SELECT DISTINCT COALESCE(qualification_tier,'UNSPECIFIED') AS t FROM site_qualification_results ORDER BY t")
            tier_opts = ["Any"] + (tiers_df["t"].tolist() if not tiers_df.empty else [])
            selected_tier = st.selectbox("Qualification Tier", tier_opts, index=0, key="tier_select")

    where, params = [], []
    if q:
        like = f"%{q}%"
        where.append("(COALESCE(site_name,'') LIKE ? OR COALESCE(site_address,'') LIKE ? OR site_id LIKE ?)")
        params += [like, like, like]
    if has_docs != "Any":
        where.append("has_documents = ?")
        params.append(1 if has_docs == "Yes" else 0)
    if has_narr != "Any":
        where.append(
            "site_id IN (SELECT site_id FROM site_summary WHERE COALESCE(has_narrative_content,0) = ?)"
        )
        params.append(1 if has_narr == "Yes" else 0)
    # Filter by selected qualification tier
    if selected_tier != "Any":
        where.append(
            "site_id IN (SELECT site_id FROM site_qualification_results WHERE COALESCE(qualification_tier,'UNSPECIFIED') = ?)"
        )
        params.append(selected_tier)
    
    # Filter by processed status (based on having a final_score in orchestration_runs)
    if processed_filter != "All":
        if processed_filter == "Yes":
            # Sites that have been processed (have a final_score)
            where.append(
                """site_id IN (
                    SELECT DISTINCT site_id 
                    FROM orchestration_runs 
                    WHERE completed_at IS NOT NULL 
                    AND (final_score IS NOT NULL OR EXISTS (
                        SELECT 1 FROM orchestration_module_results 
                        WHERE run_id = orchestration_runs.run_id 
                        AND module_name LIKE '%Score Calculation%'
                    ))
                )"""
            )
        else:  # "No"
            # Sites that have NOT been processed (no final_score)
            where.append(
                """site_id NOT IN (
                    SELECT DISTINCT site_id 
                    FROM orchestration_runs 
                    WHERE completed_at IS NOT NULL 
                    AND (final_score IS NOT NULL OR EXISTS (
                        SELECT 1 FROM orchestration_module_results 
                        WHERE run_id = orchestration_runs.run_id 
                        AND module_name LIKE '%Score Calculation%'
                    ))
                )"""
            )

    # Contamination medium/status filters via subquery
    if medium_sel or medium_status_sel:
        selected_cols = [medium_to_col[m] for m in medium_sel] if medium_sel else list(medium_to_col.values())
        sub_clauses = []
        sub_params = []
        if medium_status_sel:
            ph = ",".join(["?"] * len(medium_status_sel))
            ors = [f"COALESCE({col},'') IN ({ph})" for col in selected_cols]
            sub_clauses.append("(" + " OR ".join(ors) + ")")
            # replicate the selected statuses for each column used in OR
            for _ in selected_cols:
                sub_params += medium_status_sel
        else:
            # Only medium selected: require any non-empty value in the chosen media columns
            ors = [f"TRIM(COALESCE({col},'')) <> ''" for col in selected_cols]
            sub_clauses.append("(" + " OR ".join(ors) + ")")

        where.append("site_id IN (SELECT site_id FROM site_contaminants WHERE " + " AND ".join(sub_clauses) + ")")
        params += sub_params

    # Range filters via correlated subqueries to site_summary
    if narr_range != (narr_min, narr_max):
        where.append(
            "site_id IN (SELECT site_id FROM site_summary WHERE COALESCE(total_narrative_sections,0) BETWEEN ? AND ?)"
        )
        params += [int(narr_range[0]), int(narr_range[1])]
    if docs_range != (docs_min, docs_max):
        where.append(
            "site_id IN (SELECT site_id FROM site_summary WHERE COALESCE(total_documents,0) BETWEEN ? AND ?)"
        )
        params += [int(docs_range[0]), int(docs_range[1])]
    if span_range != (span_min, span_max):
        where.append(
            "site_id IN (SELECT site_id FROM site_summary WHERE COALESCE(document_date_range_years,0) BETWEEN ? AND ?)"
        )
        params += [int(span_range[0]), int(span_range[1])]

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params


def metric_row(where_sql: str, params: list):
    cols = st.columns(4)
    sql = f"""
        WITH filtered_sites AS (
          SELECT site_id FROM site_overview {where_sql}
        )
        SELECT 
          (SELECT COUNT(*) FROM filtered_sites) AS total_sites,
          (SELECT COUNT(*) FROM filtered_sites fs JOIN site_summary ss USING(site_id) WHERE COALESCE(ss.has_narrative_content,0)=1) AS sites_with_narratives,
          (SELECT COUNT(*) FROM filtered_sites fs JOIN site_summary ss USING(site_id) WHERE COALESCE(ss.has_documents,0)=1) AS sites_with_documents,
          (SELECT COUNT(DISTINCT sqr.site_id) FROM site_qualification_results sqr JOIN filtered_sites fs ON fs.site_id=sqr.site_id WHERE COALESCE(sqr.qualified,0)=1) AS qualified_sites
    """
    m = query_df(sql, params).iloc[0]
    cols[0].metric("Total Sites", f"{int(m.total_sites):,}")
    cols[1].metric("Sites w/ Narratives", f"{int(m.sites_with_narratives):,}")
    cols[2].metric("Sites w/ Documents", f"{int(m.sites_with_documents):,}")
    cols[3].metric("Qualified Sites", f"{int(m.qualified_sites):,}")


def tier_chart(where_sql: str, params: list):
    df = query_df(
        f"""
        WITH filtered_sites AS (
          SELECT site_id FROM site_overview {where_sql}
        )
        SELECT COALESCE(qualification_tier, 'UNSPECIFIED') AS tier,
               COUNT(*) AS count
        FROM site_qualification_results
        WHERE site_id IN (SELECT site_id FROM filtered_sites)
        GROUP BY COALESCE(qualification_tier, 'UNSPECIFIED')
        ORDER BY count DESC
        """,
        params,
    )
    if df.empty:
        st.info("No qualification results found.")
        return
    fig = px.bar(df, x="tier", y="count", title="Qualification Tiers", text="count")
    fig.update_layout(xaxis_title="Tier", yaxis_title="Count", height=380)
    st.plotly_chart(fig, use_container_width=True)


def contaminant_chart(where_sql: str, params: list):
    df = query_df(
        f"""
        WITH filtered_sites AS (
          SELECT site_id FROM site_overview {where_sql}
        )
        SELECT contaminant_type, COUNT(*) AS n
        FROM site_contaminants
        WHERE site_id IN (SELECT site_id FROM filtered_sites)
        GROUP BY contaminant_type
        ORDER BY n DESC
        LIMIT 20
        """,
        params,
    )
    if df.empty:
        st.info("No contaminants found.")
        return
    fig = px.bar(df, x="n", y="contaminant_type", orientation="h",
                 title="Top 20 Contaminant Types")
    fig.update_layout(xaxis_title="Count", yaxis_title="Contaminant Type", height=600)
    st.plotly_chart(fig, use_container_width=True)


def docs_summary(where_sql: str, params: list):
    df = query_df(
        f"""
        WITH filtered_sites AS (
          SELECT site_id FROM site_overview {where_sql}
        )
        SELECT COUNT(*) AS documents,
               SUM(CASE WHEN download_status='success' THEN 1 ELSE 0 END) AS downloaded,
               SUM(CASE WHEN flagged_for_analysis THEN 1 ELSE 0 END) AS flagged
        FROM site_documents
        WHERE site_id IN (SELECT site_id FROM filtered_sites)
        """,
        params,
    )
    if df.empty:
        return
    row = df.iloc[0]
    cols = st.columns(3)
    cols[0].metric("Documents", f"{int(row.documents or 0):,}")
    cols[1].metric("Downloads", f"{int(row.downloaded or 0):,}")
    cols[2].metric("Flagged", f"{int(row.flagged or 0):,}")


def overview_table(where_sql: str, params: list):
    # Create a hash of the current filter state to detect changes
    import hashlib
    filter_hash = hashlib.md5(f"{where_sql}{params}".encode()).hexdigest()
    
    # Initialize pagination state
    if 'home_overview_page' not in st.session_state:
        st.session_state.home_overview_page = 1
    
    # Check if filters have changed and reset to page 1 if they have
    if 'home_filter_hash' not in st.session_state:
        st.session_state.home_filter_hash = filter_hash
    elif st.session_state.home_filter_hash != filter_hash:
        st.session_state.home_filter_hash = filter_hash
        st.session_state.home_overview_page = 1  # Reset to page 1 when filters change
    
    # Get total count of sites
    total_count_df = query_df(
        f"""
        SELECT COUNT(*) as count 
        FROM site_overview
        {where_sql}
        """,
        params
    )
    total_count = int(total_count_df.iloc[0]['count']) if not total_count_df.empty else 0
    items_per_page = 500
    total_pages = int((total_count + items_per_page - 1) // items_per_page)  # Ceiling division, ensure int
    
    # Calculate offset for current page
    offset = (st.session_state.home_overview_page - 1) * items_per_page
    
    # Query with pagination
    df = query_df(
        f"""
        SELECT site_id, site_name, site_address, total_documents, total_contaminants,
               has_documents, has_contaminants, scrape_status, status_icon
        FROM site_overview
        {where_sql}
        ORDER BY CAST(site_id AS INTEGER)
        LIMIT {items_per_page}
        OFFSET {offset}
        """,
        params,
    )
    
    # Pagination controls and download button (show before the table)
    if total_pages > 1:
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        
        with col1:
            if st.button("← Previous", disabled=(st.session_state.home_overview_page == 1), key="home_prev"):
                st.session_state.home_overview_page -= 1
                st.rerun()
        
        with col2:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.home_overview_page} of {total_pages} (Total sites: {total_count:,})</div>", unsafe_allow_html=True)
        
        with col3:
            if st.button("Next →", disabled=(st.session_state.home_overview_page >= total_pages), key="home_next"):
                st.session_state.home_overview_page += 1
                st.rerun()
        
        with col4:
            # Add download all button
            if st.button("📥 Download All", key="home_download_all"):
                with st.spinner(f"Preparing download of all {total_count:,} sites..."):
                    # Query ALL data without pagination
                    all_df = query_df(
                        f"""
                        SELECT site_id, site_name, site_address, total_documents, total_contaminants,
                               has_documents, has_contaminants, scrape_status, status_icon
                        FROM site_overview
                        {where_sql}
                        ORDER BY CAST(site_id AS INTEGER)
                        """,
                        params,
                    )
                    
                    # Convert to CSV
                    csv = all_df.to_csv(index=False)
                    
                    # Offer download
                    st.download_button(
                        label="💾 Click to save CSV",
                        data=csv,
                        file_name="all_sites_overview.csv",
                        mime="text/csv",
                        key="home_download_csv"
                    )
    else:
        # If only one page, still show download button for consistency
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("📥 Download All", key="home_download_single"):
                # Convert current df to CSV (since it's all the data anyway)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="💾 Click to save CSV",
                    data=csv,
                    file_name="all_sites_overview.csv",
                    mime="text/csv",
                    key="home_download_csv_single"
                )
    
    if df.empty:
        st.info("No site overview data found.")
    else:
        # Compute Final Score per site from latest run's Score Calculation module (Module 10)
        score_rows = query_df(
            f"""
            WITH filtered_sites AS (
              SELECT site_id FROM site_overview {where_sql}
            ), lr AS (
              SELECT or1.site_id, or1.run_id, or1.final_score AS run_final_score, or1.completed_at
              FROM orchestration_runs or1
              WHERE or1.site_id IN (SELECT site_id FROM filtered_sites)
                AND or1.completed_at IS NOT NULL
            ), picked AS (
              SELECT l1.site_id, l1.run_id, l1.run_final_score
              FROM lr l1
              JOIN (
                SELECT site_id, MAX(completed_at) AS mc FROM lr GROUP BY site_id
              ) m ON m.site_id = l1.site_id AND m.mc = l1.completed_at
            )
            SELECT p.site_id, p.run_final_score, omr.module_result_json
            FROM picked p
            LEFT JOIN orchestration_module_results omr
              ON omr.run_id = p.run_id AND omr.module_name LIKE '%Score Calculation%'
            """,
            params,
        )
        score_map = {}
        if not score_rows.empty:
            import json as _json
            for _, r in score_rows.iterrows():
                final_score = None
                try:
                    if r.module_result_json:
                        d = _json.loads(r.module_result_json)
                        final_score = int((d.get('data') or {}).get('final_score') or 0)
                except Exception:
                    final_score = None
                if final_score is None:
                    final_score = int(r.run_final_score or 0)
                sid = str(r.site_id)
                score_map[sid] = final_score

        # Compute latest Qualification Tier per site
        tier_rows = query_df(
            f"""
            WITH filtered_sites AS (
              SELECT site_id FROM site_overview {where_sql}
            ), latest AS (
              SELECT sqr.site_id, COALESCE(sqr.qualification_tier,'UNSPECIFIED') AS tier, sqr.analyzed_at
              FROM site_qualification_results sqr
              WHERE sqr.site_id IN (SELECT site_id FROM filtered_sites)
            ), picked AS (
              SELECT l1.site_id, l1.tier
              FROM latest l1
              JOIN (
                SELECT site_id, MAX(analyzed_at) AS ma FROM latest GROUP BY site_id
              ) m ON m.site_id = l1.site_id AND m.ma = l1.analyzed_at
            )
            SELECT site_id, tier FROM picked
            """,
            params,
        )
        tier_map = {str(r.site_id): (r.tier or 'UNSPECIFIED') for _, r in tier_rows.iterrows()} if not tier_rows.empty else {}

        # Get feedback counts per site
        feedback_rows = query_df(
            f"""
            WITH filtered_sites AS (
              SELECT site_id FROM site_overview {where_sql}
            )
            SELECT site_id, COUNT(*) as feedback_count
            FROM ai_feedback
            WHERE site_id IN (SELECT site_id FROM filtered_sites)
            GROUP BY site_id
            """,
            params,
        )
        feedback_map = {str(r.site_id): int(r.feedback_count) for _, r in feedback_rows.iterrows()} if not feedback_rows.empty else {}

        # Add link to Site Detail page using query params
        try:
            detail_col = df["site_id"].astype(str).apply(lambda sid: f"{URL_PREFIX}/Site_Detail?site_id={sid}")
        except Exception:
            detail_col = df["site_id"].apply(lambda sid: f"{URL_PREFIX}/Site_Detail?site_id={sid}")
        df_display = df.copy()
        df_display.insert(0, "Site Detail", detail_col)

        # Insert Final Score as the 3rd column (after site_name)
        try:
            overall_scores = df_display["site_id"].astype(str).map(lambda sid: score_map.get(sid, None))
        except Exception:
            overall_scores = df_display["site_id"].map(lambda sid: score_map.get(str(sid), None))
        insert_pos = 3  # 0: Site Detail, 1: site_id, 2: site_name, 3: Final Score
        df_display.insert(insert_pos, "Final Score", overall_scores)
        # Insert Qualification Tier right after Final Score
        try:
            tiers = df_display["site_id"].astype(str).map(lambda sid: tier_map.get(sid, None))
        except Exception:
            tiers = df_display["site_id"].map(lambda sid: tier_map.get(str(sid), None))
        df_display.insert(insert_pos + 1, "Qualification Tier", tiers)

        # Add per-row Process link for sites with Final Score == 0
        api_base = os.environ.get("PROCESS_API_BASE", "http://localhost:5001").rstrip("/")
        api_token = os.environ.get("PROCESS_API_TOKEN", "secret123")
        
        # Check if any site is being processed (using session state with timestamp)
        if 'processing_site' not in st.session_state:
            st.session_state.processing_site = None
        if 'processing_until' not in st.session_state:
            st.session_state.processing_until = None
        
        # Check if processing timeout has expired
        import datetime
        if st.session_state.processing_until:
            if datetime.datetime.now() > st.session_state.processing_until:
                st.session_state.processing_site = None
                st.session_state.processing_until = None
        
        # Handle process button clicks via query params
        query_params = st.query_params
        if 'process_site' in query_params:
            site_to_process = query_params['process_site']
            
            # Check if we're still within the processing window
            if st.session_state.processing_until and datetime.datetime.now() < st.session_state.processing_until:
                st.warning(f"⏳ A site is already being processed. Please wait until {st.session_state.processing_until.strftime('%H:%M:%S')} before processing another site.")
                st.query_params.clear()
            else:
                st.session_state.processing_site = site_to_process
                st.session_state.processing_until = datetime.datetime.now() + datetime.timedelta(minutes=10)
                # Clear the query param
                st.query_params.clear()
                
                # Process the site with spinner
                with st.spinner(f"Processing Site {site_to_process}..."):
                    try:
                        url = f"{api_base}/api/process/{site_to_process}?token={api_token}"
                        response = requests.post(url, timeout=5)
                        
                        if response.status_code == 200:
                            st.success(f"✅ Site {site_to_process} has been queued for processing. Processing can take up to 10 minutes. Please refresh the page to see updated results.")
                            time.sleep(3)
                            # Keep the processing lock for 10 minutes
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to process Site {site_to_process}: {response.status_code}")
                            # Clear the lock on error
                            st.session_state.processing_site = None
                            st.session_state.processing_until = None
                    except requests.exceptions.Timeout:
                        st.info(f"📋 Site {site_to_process} is processing in the background. This can take up to 10 minutes. Please refresh the page later to see updated results.")
                        # Keep the lock for timeout (expected behavior)
                    except Exception as e:
                        st.error(f"❌ Error processing Site {site_to_process}: {str(e)}")
                        # Clear the lock on error
                        st.session_state.processing_site = None
                        st.session_state.processing_until = None
        
        # Create process links that use query params instead of direct API calls
        # Check if we're in a processing window
        is_processing = st.session_state.processing_until and datetime.datetime.now() < st.session_state.processing_until
        
        if is_processing:
            # Show remaining time
            remaining = st.session_state.processing_until - datetime.datetime.now()
            remaining_minutes = int(remaining.total_seconds() / 60)
            remaining_seconds = int(remaining.total_seconds() % 60)
            
            # Show disabled state for all process links
            def make_disabled_link(r):
                try:
                    score = r.get("Final Score")
                    # Only show process link if score is NaN or None (not processed)
                    if pd.isna(score) or score is None:
                        return f"⏳ Wait {remaining_minutes}m {remaining_seconds}s"
                    else:
                        return ""  # Has a score (including 0), so no process link
                except:
                    return f"⏳ Wait {remaining_minutes}m {remaining_seconds}s"
            
            process_links = df_display.apply(make_disabled_link, axis=1)
        else:
            # Normal process links (only for unprocessed sites)
            def make_process_link(r):
                try:
                    score = r.get("Final Score")
                    site_id = str(r['site_id'])
                    # Only show process link if score is NaN or None (not processed)
                    if pd.isna(score) or score is None:
                        return f"?process_site={site_id}"
                    else:
                        return ""  # Has a score, no process link
                except:
                    return f"?process_site={str(r['site_id'])}"
            
            process_links = df_display.apply(make_process_link, axis=1)

        df_display.insert(insert_pos + 2, "Process", process_links)
        
        # Add QC column for processed sites
        def make_qc_link(r):
            try:
                score = r.get("Final Score")
                site_id = str(r['site_id'])
                # Only show QC link if site has been processed (has a score)
                if pd.isna(score) or score is None:
                    return ""  # Not processed, no QC link
                else:
                    # Has a score (including 0), show QC link to view results
                    base_url = os.environ.get("PROCESS_API_BASE", "http://localhost:5001").rstrip("/")
                    return f"{base_url}/results/{site_id}"
            except:
                return ""
        
        qc_links = df_display.apply(make_qc_link, axis=1)
        df_display.insert(insert_pos + 3, "QC", qc_links)
        
        # Add Feedback count column with links
        def make_feedback_cell(r):
            try:
                site_id = str(r['site_id'])
                count = feedback_map.get(site_id, 0)
                if count > 0:
                    # Return the link for LinkColumn
                    return f"{URL_PREFIX}/Feedback?site_id={site_id}"
                else:
                    return ""
            except:
                return ""
        
        feedback_links = df_display.apply(make_feedback_cell, axis=1)
        df_display.insert(insert_pos + 4, "Feedback", feedback_links)

        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            column_config={
                "Site Detail": st.column_config.LinkColumn(
                    label="Site Detail",
                    display_text="Open",
                ),
                "Final Score": st.column_config.NumberColumn(
                    label="Final Score",
                    help="Latest Score Calculation module final score",
                    format="%d",
                ),
                "Qualification Tier": st.column_config.TextColumn(
                    label="Qualification Tier",
                    help="Latest qualification tier from analyzed results",
                ),
                "Process": st.column_config.LinkColumn(
                    label="Process",
                    display_text="Process",
                    help="Trigger processing for sites with no score" if not is_processing else f"Processing in progress. Wait until {st.session_state.processing_until.strftime('%H:%M:%S') if st.session_state.processing_until else ''}"
                ) if not is_processing else st.column_config.TextColumn(
                    label="Process",
                    help=f"Processing in progress. Wait until {st.session_state.processing_until.strftime('%H:%M:%S') if st.session_state.processing_until else ''}"
                ),
                "QC": st.column_config.LinkColumn(
                    label="QC",
                    display_text="QC",
                    help="View qualification results for processed sites"
                ),
                "Feedback": st.column_config.LinkColumn(
                    label="Feedback",
                    display_text="View",
                    help="Click to view feedback details for this site"
                ),
            },
        )


def main():
    import os
    
    # Check authentication first
    check_auth()
    
    # Add button linking to FastHTML application
    base_url = os.environ.get("PROCESS_API_BASE", "http://localhost:5001").rstrip("/")
    st.markdown(f'''
    <div style="text-align: right; margin-bottom: -30px;">
        <a href="{base_url}" target="_blank" style="text-decoration: none;">
            <button style="
                background-color: #059669;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: background-color 0.3s;
            ">
                🚀 End to End Scrape + Qualification
            </button>
        </a>
    </div>
    ''', unsafe_allow_html=True)
    
    st.title("Scrapped WA Eco Sites 📊")
    
    # Display the database path - show full absolute path
    full_db_path = os.path.abspath(DB_PATH)
    st.sidebar.markdown("### Database Configuration")
    st.sidebar.info(f"**Database Path:**\n`{full_db_path}`")
    st.sidebar.markdown("---")

    if not db_exists():
        st.error(f"Database not found at {DB_PATH}. Please ensure the database file exists or set the ECO_DB_PATH environment variable.")
        st.stop()

    st.caption("Analytics UI for exploring narratives, documents, qualifications, contaminants, and more.")

    where_sql, params = build_site_filters_ui()

    # Combined metrics row - sites metrics and docs metrics together
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    # Get site metrics
    sql = f"""
        WITH filtered_sites AS (
          SELECT site_id FROM site_overview {where_sql}
        )
        SELECT 
          (SELECT COUNT(*) FROM filtered_sites) AS total_sites,
          (SELECT COUNT(*) FROM filtered_sites fs JOIN site_summary ss USING(site_id) WHERE COALESCE(ss.has_narrative_content,0)=1) AS sites_with_narratives,
          (SELECT COUNT(*) FROM filtered_sites fs JOIN site_summary ss USING(site_id) WHERE COALESCE(ss.has_documents,0)=1) AS sites_with_documents,
          (SELECT COUNT(DISTINCT sqr.site_id) FROM site_qualification_results sqr JOIN filtered_sites fs ON fs.site_id=sqr.site_id WHERE COALESCE(sqr.qualified,0)=1) AS qualified_sites
    """
    m = query_df(sql, params).iloc[0]
    
    # Get docs metrics
    docs_sql = f"""
        WITH filtered_sites AS (
          SELECT site_id FROM site_overview {where_sql}
        )
        SELECT COUNT(*) AS documents,
               SUM(CASE WHEN download_status='success' THEN 1 ELSE 0 END) AS downloaded,
               SUM(CASE WHEN flagged_for_analysis THEN 1 ELSE 0 END) AS flagged
        FROM site_documents
        WHERE site_id IN (SELECT site_id FROM filtered_sites)
    """
    docs = query_df(docs_sql, params).iloc[0]
    
    # Display all metrics in one row
    with col1:
        st.metric("Sites", f"{int(m.total_sites):,}")
    with col2:
        st.metric("w/ Narr", f"{int(m.sites_with_narratives):,}")
    with col3:
        st.metric("w/ Docs", f"{int(m.sites_with_documents):,}")
    with col4:
        st.metric("Qualified", f"{int(m.qualified_sites):,}")
    with col5:
        st.metric("Docs", f"{int(docs.documents or 0):,}")
    with col6:
        st.metric("Downloaded", f"{int(docs.downloaded or 0):,}")
    with col7:
        st.metric("Flagged for analysis", f"{int(docs.flagged or 0):,}")

    st.divider()
    st.subheader("Recent Site Overview")
    overview_table(where_sql, params)


if __name__ == "__main__":
    main()
