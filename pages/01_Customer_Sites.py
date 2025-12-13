import os
import streamlit as st
import pandas as pd
import requests
import time

from app_lib.db import query_df, db_exists, DB_PATH

st.set_page_config(page_title="Customer Sites", page_icon="🏢", layout="wide")

# URL prefix for deployment behind nginx (e.g., '/streamlit')
URL_PREFIX = os.environ.get('URL_PREFIX', '')


@st.cache_data(persist="disk")
def get_cached_data(query: str, params: tuple):
    """Cache database queries indefinitely until manual refresh"""
    return query_df(query, params)


def build_filters_ui():
    """Render simplified filters for Customer Sites page."""

    with st.expander("🔍 Filters", expanded=True):
        # First row: Sites per customer slider (filters the customer dropdown)
        sites_per_customer_stats = get_cached_data("""
            SELECT
                MIN(site_count) as min_sites,
                MAX(site_count) as max_sites
            FROM (
                SELECT box_case_name, COUNT(*) as site_count
                FROM box_case_matches
                WHERE box_case_name IS NOT NULL AND TRIM(box_case_name) != ''
                GROUP BY box_case_name
            )
        """, ())

        if not sites_per_customer_stats.empty:
            min_sites = int(sites_per_customer_stats.iloc[0]['min_sites'] or 1)
            max_sites = int(sites_per_customer_stats.iloc[0]['max_sites'] or 1)
        else:
            min_sites, max_sites = 1, 1

        # Ensure valid range
        max_sites_eff = max_sites if max_sites > min_sites else min_sites + 1

        sites_per_customer_range = st.slider(
            "Sites per Customer",
            min_value=min_sites,
            max_value=max_sites_eff,
            value=(min_sites, max_sites if max_sites > min_sites else min_sites + 1),
            key="sites_per_customer_slider",
            help="Filter customer dropdown to show only customers with this many sites"
        )

        # Second row: Customer Name and Historical Use Category
        col1, col2 = st.columns(2)

        with col1:
            # Customer Name filter - filtered by sites per customer slider
            customer_options = get_cached_data(f"""
                SELECT box_case_name, COUNT(*) as site_count
                FROM box_case_matches
                WHERE box_case_name IS NOT NULL AND TRIM(box_case_name) != ''
                GROUP BY box_case_name
                HAVING COUNT(*) BETWEEN {int(sites_per_customer_range[0])} AND {int(sites_per_customer_range[1])}
                ORDER BY box_case_name
            """, ())
            customer_list = customer_options["box_case_name"].tolist() if not customer_options.empty else []
            selected_customers = st.multiselect(
                f"Customer Name ({len(customer_list)} customers)",
                options=customer_list,
                default=[],
                key="customer_select",
                help="Filter sites by Box customer/case name"
            )

        with col2:
            # Historical Use Category filter
            historical_use_options = get_cached_data("""
                SELECT DISTINCT historical_use_category
                FROM sites
                WHERE historical_use_category IS NOT NULL AND TRIM(historical_use_category) != ''
                ORDER BY historical_use_category
            """, ())
            historical_use_list = historical_use_options["historical_use_category"].tolist() if not historical_use_options.empty else []
            selected_historical_use = st.multiselect(
                "Historical Use Category",
                options=historical_use_list,
                default=[],
                key="historical_use_select",
                help="Filter sites by their historical use category"
            )

    # Build WHERE clause
    where, params = [], []

    # Always filter to customers within the sites per customer range
    where.append("""bcm.box_case_name IN (
        SELECT box_case_name
        FROM box_case_matches
        WHERE box_case_name IS NOT NULL AND TRIM(box_case_name) != ''
        GROUP BY box_case_name
        HAVING COUNT(*) BETWEEN ? AND ?
    )""")
    params.extend([int(sites_per_customer_range[0]), int(sites_per_customer_range[1])])

    # Filter by selected customers
    if selected_customers:
        placeholders = ",".join(["?" for _ in selected_customers])
        where.append(f"bcm.box_case_name IN ({placeholders})")
        params.extend(selected_customers)

    # Filter by historical use category
    if selected_historical_use:
        placeholders = ",".join(["?" for _ in selected_historical_use])
        where.append(f"""so.site_id IN (
            SELECT site_id
            FROM sites
            WHERE historical_use_category IN ({placeholders})
        )""")
        params.extend(selected_historical_use)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params


def overview_table(where_sql: str, params: list):
    import hashlib
    filter_hash = hashlib.md5(f"{where_sql}{params}".encode()).hexdigest()

    # Initialize pagination state
    if 'customer_sites_page' not in st.session_state:
        st.session_state.customer_sites_page = 1

    # Check if filters have changed and reset to page 1
    if 'customer_filter_hash' not in st.session_state:
        st.session_state.customer_filter_hash = filter_hash
    elif st.session_state.customer_filter_hash != filter_hash:
        st.session_state.customer_filter_hash = filter_hash
        st.session_state.customer_sites_page = 1

    # Sort by site_id descending
    order_by_clause = "ORDER BY CAST(so.site_id AS INTEGER) DESC"

    # Get total count
    total_count_df = query_df(
        f"""
        SELECT COUNT(*) as count
        FROM site_overview so
        LEFT JOIN sites s ON so.site_id = s.site_id
        LEFT JOIN box_case_matches bcm ON so.site_id = bcm.site_id
        LEFT JOIN site_summary ss ON so.site_id = ss.site_id
        LEFT JOIN (
            SELECT site_id, sfdc_opportunity_name, stage, created_date, close_date
            FROM site_opportunities
            WHERE (site_id, created_date) IN (
                SELECT site_id, MAX(created_date)
                FROM site_opportunities
                GROUP BY site_id
            )
        ) sfo ON so.site_id = sfo.site_id
        {where_sql}
        """,
        params
    )
    total_count = int(total_count_df.iloc[0]['count']) if not total_count_df.empty else 0
    items_per_page = 500
    total_pages = int((total_count + items_per_page - 1) // items_per_page)

    offset = (st.session_state.customer_sites_page - 1) * items_per_page

    # Query with pagination
    df = query_df(
        f"""
        SELECT so.site_id, s.county, so.site_name, so.site_address, s.sfdc_lead_url, ss.site_status,
               sfo.sfdc_opportunity_name, sfo.stage AS sfdc_opportunity_stage, sfo.created_date AS opp_created_date, sfo.close_date AS opp_close_date,
               bcm.box_case_name, bcm.matched_via_contact, bcm.matched_via_org
        FROM site_overview so
        LEFT JOIN sites s ON so.site_id = s.site_id
        LEFT JOIN site_summary ss ON so.site_id = ss.site_id
        LEFT JOIN box_case_matches bcm ON so.site_id = bcm.site_id
        LEFT JOIN (
            SELECT site_id, sfdc_opportunity_name, stage, created_date, close_date
            FROM site_opportunities
            WHERE (site_id, created_date) IN (
                SELECT site_id, MAX(created_date)
                FROM site_opportunities
                GROUP BY site_id
            )
        ) sfo ON so.site_id = sfo.site_id
        {where_sql}
        {order_by_clause}
        LIMIT {items_per_page}
        OFFSET {offset}
        """,
        params,
    )

    # Pagination controls
    if total_pages > 1:
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])

        with col1:
            if st.button("← Previous", disabled=(st.session_state.customer_sites_page == 1), key="customer_prev"):
                st.session_state.customer_sites_page -= 1
                st.rerun()

        with col2:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.customer_sites_page} of {total_pages} (Total sites: {total_count:,})</div>", unsafe_allow_html=True)

        with col3:
            if st.button("Next →", disabled=(st.session_state.customer_sites_page >= total_pages), key="customer_next"):
                st.session_state.customer_sites_page += 1
                st.rerun()

        with col4:
            if st.button("📥 Download All", key="customer_download_all"):
                with st.spinner(f"Preparing download of all {total_count:,} sites..."):
                    all_df = query_df(
                        f"""
                        SELECT so.site_id, s.county, so.site_name, so.site_address, s.sfdc_lead_url, ss.site_status,
                               sfo.sfdc_opportunity_name, bcm.box_case_name, bcm.matched_via_contact, bcm.matched_via_org
                        FROM site_overview so
                        LEFT JOIN sites s ON so.site_id = s.site_id
                        LEFT JOIN site_summary ss ON so.site_id = ss.site_id
                        LEFT JOIN box_case_matches bcm ON so.site_id = bcm.site_id
                        LEFT JOIN (
                            SELECT site_id, sfdc_opportunity_name, stage, created_date, close_date
                            FROM site_opportunities
                            WHERE (site_id, created_date) IN (
                                SELECT site_id, MAX(created_date)
                                FROM site_opportunities
                                GROUP BY site_id
                            )
                        ) sfo ON so.site_id = sfo.site_id
                        {where_sql}
                        ORDER BY CAST(so.site_id AS INTEGER)
                        """,
                        params,
                    )
                    csv = all_df.to_csv(index=False)
                    st.download_button(
                        label="💾 Click to save CSV",
                        data=csv,
                        file_name="customer_sites.csv",
                        mime="text/csv",
                        key="customer_download_csv"
                    )
    else:
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("📥 Download All", key="customer_download_single"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="💾 Click to save CSV",
                    data=csv,
                    file_name="customer_sites.csv",
                    mime="text/csv",
                    key="customer_download_csv_single"
                )

    if df.empty:
        st.info("No sites found matching the filters.")
    else:
        # Get scores from Module 9
        site_ids = df['site_id'].unique().tolist()
        site_ids_str = ','.join(['?' for _ in site_ids])

        module9_scores = query_df(
            f"""
            SELECT sqr.site_id, sqr.final_calculated_score, sqr.analyzed_at
            FROM site_qualification_results sqr
            WHERE sqr.site_id IN ({site_ids_str})
            AND sqr.analyzed_at = (
                SELECT MAX(analyzed_at)
                FROM site_qualification_results
                WHERE site_id = sqr.site_id
            )
            """,
            site_ids,
        )

        score_map = {}
        last_processed_map = {}

        if not module9_scores.empty:
            for _, r in module9_scores.iterrows():
                sid = str(r.site_id)
                score_map[sid] = int(r.final_calculated_score) if r.final_calculated_score is not None else None
                if r.analyzed_at:
                    last_processed_map[sid] = pd.to_datetime(r.analyzed_at).strftime('%Y-%m-%d %H:%M')

        # Get historical use categories
        historical_use_rows = query_df(
            f"""
            SELECT site_id, historical_use_category
            FROM sites
            WHERE site_id IN ({site_ids_str})
            """,
            site_ids,
        )
        historical_use_map = {str(r.site_id): r.historical_use_category for _, r in historical_use_rows.iterrows()} if not historical_use_rows.empty else {}

        # Get age check scores
        age_check_rows = query_df(
            f"""
            WITH latest_runs AS (
                SELECT site_id, run_id,
                       ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY completed_at DESC) as rn
                FROM orchestration_runs
                WHERE completed_at IS NOT NULL
                AND site_id IN ({site_ids_str})
            )
            SELECT
                lr.site_id,
                CAST(json_extract(omr.module_result_json, '$.data.score') AS INTEGER) as age_score
            FROM latest_runs lr
            LEFT JOIN orchestration_module_results omr
                ON lr.run_id = omr.run_id
                AND omr.module_name LIKE '%Age Qualification%'
            WHERE lr.rn = 1
            """,
            site_ids,
        )
        age_check_map = {}
        if not age_check_rows.empty:
            for _, r in age_check_rows.iterrows():
                sid = str(r.site_id)
                if r.age_score is not None:
                    age_check_map[sid] = "Passed" if r.age_score == 50 else "Failed"
                else:
                    age_check_map[sid] = None

        # Get age confidence scores
        age_confidence_rows = query_df(
            f"""
            WITH latest_runs AS (
                SELECT site_id, run_id,
                       ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY completed_at DESC) as rn
                FROM orchestration_runs
                WHERE completed_at IS NOT NULL
                AND site_id IN ({site_ids_str})
            )
            SELECT
                lr.site_id,
                CAST(json_extract(omr.module_result_json, '$.data.age_confidence') AS INTEGER) as age_confidence
            FROM latest_runs lr
            LEFT JOIN orchestration_module_results omr
                ON lr.run_id = omr.run_id
                AND omr.module_name LIKE '%Age Qualification%'
            WHERE lr.rn = 1
            """,
            site_ids,
        )
        age_confidence_map = {}
        if not age_confidence_rows.empty:
            for _, r in age_confidence_rows.iterrows():
                sid = str(r.site_id)
                if r.age_confidence is not None and r.age_confidence > 0:
                    age_confidence_map[sid] = int(r.age_confidence)
                else:
                    age_confidence_map[sid] = None

        # Create display dataframe
        df_display = df.copy()

        # Convert site_id to numeric for proper sorting
        if "site_id" in df_display.columns:
            df_display["site_id"] = pd.to_numeric(df_display["site_id"], errors='coerce')

        # Create link columns
        try:
            detail_col = df_display["site_id"].astype(str).apply(lambda sid: f"{URL_PREFIX}/Site_Detail?site_id={sid}")
        except Exception:
            detail_col = df_display["site_id"].apply(lambda sid: f"{URL_PREFIX}/Site_Detail?site_id={sid}")

        # SFDC Lead formatting
        def format_sfdc_lead(url):
            if not url or pd.isna(url):
                return None
            elif str(url).strip().upper() == "IGNORE":
                return "IGNORE"
            else:
                return url

        try:
            lead_id_links = df_display["sfdc_lead_url"].apply(format_sfdc_lead)
        except Exception:
            lead_id_links = pd.Series([None] * len(df_display))

        if "sfdc_lead_url" in df_display.columns:
            df_display = df_display.drop(columns=["sfdc_lead_url"])

        # Create QC links
        def make_qc_link(r):
            try:
                score = score_map.get(str(r['site_id']), None)
                site_id = str(r['site_id'])
                if score is None:
                    return ""
                else:
                    fasthtml_url = os.environ.get("PUBLIC_FASTHTML_URL", "/fasthtml").rstrip("/")
                    return f"{fasthtml_url}/results/{site_id}"
            except:
                return ""

        qc_links = df_display.apply(make_qc_link, axis=1)

        # Insert columns in order
        df_display.insert(1, "Milo Report", qc_links)
        df_display.insert(2, "Site Detail", detail_col)

        # Age Confidence (right after Site Detail)
        try:
            age_confidence = df_display["site_id"].astype(str).map(lambda sid: age_confidence_map.get(sid, None))
        except Exception:
            age_confidence = df_display["site_id"].map(lambda sid: age_confidence_map.get(str(sid), None))
        df_display.insert(3, "Age Confidence", age_confidence)

        if "site_status" in df_display.columns:
            site_status_col = df_display.pop("site_status")
            df_display.insert(4, "Site Status", site_status_col)

        # Box Customer (before SFDC Lead)
        if "box_case_name" in df_display.columns:
            box_customer_col = df_display.pop("box_case_name")
            df_display.insert(5, "Box Customer", box_customer_col)

        df_display.insert(6, "SFDC Lead", lead_id_links)

        # SFDC Opportunity with color-coded indicator (right after SFDC Lead)
        if "sfdc_opportunity_name" in df_display.columns:
            def add_opportunity_indicator(row):
                opp_name = row['sfdc_opportunity_name']
                stage = row.get('sfdc_opportunity_stage', '')

                if pd.notna(opp_name) and str(opp_name).strip() != "":
                    if stage == "Closed Lost":
                        return f"🔴 {opp_name}"
                    elif stage == "Opportunity Won/Signed":
                        return f"🟢 {opp_name}"
                    else:
                        return f"🟡 {opp_name}"
                return opp_name

            sfdc_opp_col = df_display.apply(add_opportunity_indicator, axis=1)
            df_display.pop("sfdc_opportunity_name")
            if "sfdc_opportunity_stage" in df_display.columns:
                df_display.pop("sfdc_opportunity_stage")
            df_display.insert(7, "SFDC Opportunity", sfdc_opp_col)

        # Remove Opp Created and Opp Close Date columns if present
        if "opp_created_date" in df_display.columns:
            df_display = df_display.drop(columns=["opp_created_date"])
        if "opp_close_date" in df_display.columns:
            df_display = df_display.drop(columns=["opp_close_date"])

        # Historical Use
        try:
            historical_use = df_display["site_id"].astype(str).map(lambda sid: historical_use_map.get(sid, None))
        except Exception:
            historical_use = df_display["site_id"].map(lambda sid: historical_use_map.get(str(sid), None))
        df_display.insert(11, "Historical Use", historical_use)

        # Last Processed
        try:
            last_processed = df_display["site_id"].astype(str).map(lambda sid: last_processed_map.get(sid, None))
        except Exception:
            last_processed = df_display["site_id"].map(lambda sid: last_processed_map.get(str(sid), None))
        df_display.insert(12, "Last Processed", last_processed)

        # Final Score
        try:
            overall_scores = df_display["site_id"].astype(str).map(lambda sid: score_map.get(sid, None))
        except Exception:
            overall_scores = df_display["site_id"].map(lambda sid: score_map.get(str(sid), None))
        df_display.insert(13, "Final Score", overall_scores)

        # Age Check
        try:
            age_check = df_display["site_id"].astype(str).map(lambda sid: age_check_map.get(sid, None))
        except Exception:
            age_check = df_display["site_id"].map(lambda sid: age_check_map.get(str(sid), None))
        df_display.insert(14, "Age Check", age_check)

        # Move matched_via columns to be together before site_address
        if "site_address" in df_display.columns:
            site_address_pos = df_display.columns.get_loc("site_address")
            if "matched_via_contact" in df_display.columns:
                matched_via_contact_col = df_display.pop("matched_via_contact")
                df_display.insert(site_address_pos, "Matched Via Contact", matched_via_contact_col)
            if "matched_via_org" in df_display.columns:
                # Insert right after Matched Via Contact
                matched_via_contact_pos = df_display.columns.get_loc("Matched Via Contact")
                matched_via_org_col = df_display.pop("matched_via_org")
                df_display.insert(matched_via_contact_pos + 1, "Matched Via Org", matched_via_org_col)

        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            column_config={
                "Milo Report": st.column_config.LinkColumn(
                    label="Milo Report",
                    display_text="Milo Report",
                    help="View qualification results for processed sites"
                ),
                "Site Detail": st.column_config.LinkColumn(
                    label="Site Detail",
                    display_text="Site Detail",
                ),
                "Site Status": st.column_config.TextColumn(
                    label="Site Status",
                    help="Cleanup/remediation status of the site"
                ),
                "SFDC Lead": st.column_config.LinkColumn(
                    label="SFDC Lead",
                    help="Click to open Salesforce Lead record"
                ),
                "Box Customer": st.column_config.TextColumn(
                    label="Box Customer",
                    help="Matched Box case/customer name from existing client database"
                ),
                "SFDC Opportunity": st.column_config.TextColumn(
                    label="SFDC Opportunity",
                    help="Most recent Salesforce Opportunity name for this site"
                ),
                "Historical Use": st.column_config.TextColumn(
                    label="Historical Use",
                    help="Historical use category from Module 9 analysis",
                ),
                "Last Processed": st.column_config.TextColumn(
                    label="Last Processed",
                    help="Date and time when site was last processed",
                ),
                "Final Score": st.column_config.NumberColumn(
                    label="Final Score",
                    help="Latest Score Calculation module final score",
                    format="%d",
                ),
                "Age Check": st.column_config.TextColumn(
                    label="Age Check",
                    help="Age Qualification status: Passed or Failed",
                ),
                "Age Confidence": st.column_config.NumberColumn(
                    label="Age Confidence",
                    help="Age evidence confidence score (0-100%)",
                    format="%d%%",
                ),
            },
        )


def main():
    st.title("Customer Sites 🏢")

    # Add refresh button
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.success("Cache cleared! Data will be refreshed.")
            st.rerun()

    # Display database path
    full_db_path = os.path.abspath(DB_PATH)
    st.sidebar.markdown("### Database Configuration")
    st.sidebar.info(f"**Database Path:**\n`{full_db_path}`")
    st.sidebar.markdown("---")

    if not db_exists():
        st.error(f"Database not found at {DB_PATH}. Please ensure the database file exists or set the ECO_DB_PATH environment variable.")
        st.stop()

    st.caption("Filter sites by Customer Name and Historical Use Category.")

    where_sql, params = build_filters_ui()

    # Metrics row
    sql = f"""
        SELECT COUNT(*) as total_sites
        FROM site_overview so
        LEFT JOIN sites s ON so.site_id = s.site_id
        LEFT JOIN box_case_matches bcm ON so.site_id = bcm.site_id
        LEFT JOIN site_summary ss ON so.site_id = ss.site_id
        LEFT JOIN (
            SELECT site_id, sfdc_opportunity_name, stage, created_date, close_date
            FROM site_opportunities
            WHERE (site_id, created_date) IN (
                SELECT site_id, MAX(created_date)
                FROM site_opportunities
                GROUP BY site_id
            )
        ) sfo ON so.site_id = sfo.site_id
        {where_sql}
    """
    m = get_cached_data(sql, tuple(params)).iloc[0]

    st.metric("Total Sites", f"{int(m.total_sites):,}")

    st.divider()
    st.subheader("Customer Sites Overview")
    overview_table(where_sql, params)


if __name__ == "__main__":
    main()
