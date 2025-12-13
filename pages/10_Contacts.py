import os
import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Contacts", page_icon="📇", layout="wide")

# URL prefix for deployment behind nginx (e.g., '/streamlit')
URL_PREFIX = os.environ.get('URL_PREFIX', '')


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Contacts 📇")
    st.caption("Summarized contacts detected during qualification, prioritized by confidence.")

    # --- Filters ---
    st.subheader("Filters")
    q = st.text_input(
        "Search (site, contact, org, email, phone)", value="",
        help="Matches site name/id, contact name, organization, email, phone, and address"
    )

    # Load distinct options for filters
    site_opts_df = query_df(
        """
        SELECT DISTINCT site_id, site_name
        FROM site_contacts_summary
        ORDER BY CAST(site_id AS INTEGER)
        """
    )
    site_label_map = {f"{row.site_id} — {row.site_name}": row.site_id for _, row in site_opts_df.iterrows()} if not site_opts_df.empty else {}
    site_labels = list(site_label_map.keys())

    role_opts = query_df("SELECT DISTINCT contact_role AS v FROM site_contacts_summary WHERE TRIM(COALESCE(contact_role,'')) <> '' ORDER BY v")
    type_opts = query_df("SELECT DISTINCT contact_type AS v FROM site_contacts_summary WHERE TRIM(COALESCE(contact_type,'')) <> '' ORDER BY v")

    # Numeric ranges
    stats = query_df(
        """
        SELECT 
          MIN(COALESCE(confidence_score,0.0)) AS conf_min,
          MAX(COALESCE(confidence_score,0.0)) AS conf_max,
          MIN(COALESCE(prospect_priority,0)) AS prio_min,
          MAX(COALESCE(prospect_priority,0)) AS prio_max
        FROM site_contacts_summary
        """
    )
    if stats.empty:
        conf_min = conf_max = 0.0
        prio_min = prio_max = 0
    else:
        r = stats.iloc[0]
        conf_min, conf_max = float(r.conf_min or 0.0), float(r.conf_max or 0.0)
        prio_min, prio_max = int(r.prio_min or 0), int(r.prio_max or 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sites_sel = st.multiselect("Sites", site_labels, default=[])
    with c2:
        roles_sel = st.multiselect("Contact Role", role_opts["v"].tolist() if not role_opts.empty else [], default=[])
    with c3:
        types_sel = st.multiselect("Contact Type", type_opts["v"].tolist() if not type_opts.empty else [], default=[])

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        is_primary = st.selectbox("Primary Prospect", ["Any", "Yes", "No"], index=0)
    with c6:
        qualified = st.selectbox("Qualified", ["Any", "Yes", "No"], index=0)
    with c7:
        # Confidence slider (ensure valid range if equal)
        conf_max_eff = conf_max if conf_max > conf_min else conf_min + 0.01
        conf_range = st.slider(
            "Confidence Score",
            min_value=float(conf_min), max_value=float(conf_max_eff),
            value=(float(conf_min), float(conf_max)), step=0.01
        )
    with c8:
        prio_max_eff = prio_max if prio_max > prio_min else prio_min + 1
        prio_range = st.slider(
            "Prospect Priority",
            min_value=int(prio_min), max_value=int(prio_max_eff),
            value=(int(prio_min), int(prio_max))
        )

    # Build WHERE clause
    where, params = [], []
    if q:
        like = f"%{q}%"
        where.append(
            "(COALESCE(site_name,'') LIKE ? OR COALESCE(site_id,'') LIKE ? OR "
            " COALESCE(contact_name,'') LIKE ? OR COALESCE(organization_name,'') LIKE ? OR "
            " COALESCE(contact_address,'') LIKE ? OR COALESCE(email,'') LIKE ? OR COALESCE(phone,'') LIKE ?)"
        )
        params += [like, like, like, like, like, like, like]

    if sites_sel:
        selected_ids = [site_label_map[s] for s in sites_sel]
        placeholders = ",".join(["?"] * len(selected_ids))
        where.append(f"site_id IN ({placeholders})")
        params += selected_ids

    if roles_sel:
        placeholders = ",".join(["?"] * len(roles_sel))
        where.append(f"contact_role IN ({placeholders})")
        params += roles_sel

    if types_sel:
        placeholders = ",".join(["?"] * len(types_sel))
        where.append(f"contact_type IN ({placeholders})")
        params += types_sel


    if is_primary != "Any":
        where.append("COALESCE(is_primary_prospect,0) = ?")
        params.append(1 if is_primary == "Yes" else 0)

    if qualified != "Any":
        where.append("COALESCE(qualified,0) = ?")
        params.append(1 if qualified == "Yes" else 0)

    # Ranges
    if conf_range != (conf_min, conf_max):
        where.append("COALESCE(confidence_score,0.0) BETWEEN ? AND ?")
        params += [float(conf_range[0]), float(conf_range[1])]

    if prio_range != (prio_min, prio_max):
        where.append("COALESCE(prospect_priority,0) BETWEEN ? AND ?")
        params += [int(prio_range[0]), int(prio_range[1])]

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # Query filtered results
    df = query_df(
        f"""
        SELECT site_id, site_name, contact_name, organization_name, contact_address, phone, email,
               contact_type, contact_role, is_primary_prospect, prospect_priority, confidence_score,
               site_url
        FROM site_contacts_summary
        {where_sql}
        ORDER BY CAST(site_id AS INTEGER), prospect_priority ASC, confidence_score DESC
        LIMIT 10000
        """,
        params,
    )

    st.write(f"Results: {len(df):,}")

    if not df.empty:
        # Get unique site IDs from the contacts data
        site_ids = df['site_id'].unique().tolist()
        site_ids_placeholders = ','.join(['?'] * len(site_ids))

        # Get scores from Module 9 (site_qualification_results)
        module9_scores = query_df(
            f"""
            SELECT sqr.site_id, sqr.final_calculated_score
            FROM site_qualification_results sqr
            WHERE sqr.site_id IN ({site_ids_placeholders})
            AND sqr.analyzed_at = (
                SELECT MAX(analyzed_at)
                FROM site_qualification_results
                WHERE site_id = sqr.site_id
            )
            """,
            site_ids,
        )

        score_map = {}

        # First, populate from Module 9 results
        if not module9_scores.empty:
            for _, r in module9_scores.iterrows():
                sid = str(r.site_id)
                score_map[sid] = int(r.final_calculated_score) if r.final_calculated_score is not None else None

        # Then, get scores from old workflow for sites not in Module 9
        score_rows = query_df(
            f"""
            WITH lr AS (
              SELECT or1.site_id, or1.run_id, or1.final_score AS run_final_score
              FROM orchestration_runs or1
              WHERE or1.site_id IN ({site_ids_placeholders})
                AND or1.completed_at IS NOT NULL
            ), picked AS (
              SELECT l1.site_id, l1.run_id, l1.run_final_score
              FROM lr l1
              JOIN (
                SELECT site_id, MAX(run_id) AS mr FROM lr GROUP BY site_id
              ) m ON m.site_id = l1.site_id AND m.mr = l1.run_id
            )
            SELECT p.site_id, p.run_final_score, omr.module_result_json
            FROM picked p
            LEFT JOIN orchestration_module_results omr
              ON omr.run_id = p.run_id AND omr.module_name LIKE '%Score Calculation%'
            """,
            site_ids,
        )

        # Fill in scores from old workflow only if not already set by Module 9
        if not score_rows.empty:
            import json as _json
            for _, r in score_rows.iterrows():
                sid = str(r.site_id)
                # Only use old workflow score if Module 9 didn't provide one
                if sid not in score_map:
                    final_score = None
                    try:
                        if r.module_result_json:
                            d = _json.loads(r.module_result_json)
                            final_score = int((d.get('data') or {}).get('final_score') or 0)
                    except Exception:
                        final_score = None
                    if final_score is None:
                        final_score = int(r.run_final_score or 0)
                    score_map[sid] = final_score

        # Create a copy for display modifications
        df_display = df.copy()

        # Create Site Detail link column
        try:
            detail_col = df_display["site_id"].astype(str).apply(lambda sid: f"{URL_PREFIX}/Site_Detail?site_id={sid}")
        except Exception:
            detail_col = df_display["site_id"].apply(lambda sid: f"{URL_PREFIX}/Site_Detail?site_id={sid}")

        # Create Milo Report (QC) links for processed sites
        def make_qc_link(r):
            try:
                score = score_map.get(str(r['site_id']), None)
                site_id = str(r['site_id'])
                # Only show QC link if site has been processed (has a score)
                if score is None:
                    return ""  # Not processed, no QC link
                else:
                    # Has a score (including 0), show QC link to view results
                    fasthtml_url = os.environ.get("PUBLIC_FASTHTML_URL", "/fasthtml").rstrip("/")
                    return f"{fasthtml_url}/results/{site_id}"
            except:
                return ""

        qc_links = df_display.apply(make_qc_link, axis=1)

        # Insert Milo Report at position 1 (after site_id)
        df_display.insert(1, "Milo Report", qc_links)

        # Insert Site Detail at position 2
        df_display.insert(2, "Site Detail", detail_col)

        st.dataframe(
            df_display,
            use_container_width=True,
            height=700,
            column_config={
                "Milo Report": st.column_config.LinkColumn(
                    label="Milo Report",
                    display_text="Milo Report",
                    help="View qualification results for processed sites"
                ),
                "Site Detail": st.column_config.LinkColumn(
                    label="Site Detail",
                    display_text="Site Detail",
                    help="View detailed site information"
                ),
            }
        )
    else:
        st.dataframe(df, use_container_width=True, height=700)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="contacts_export.csv",
        mime="text/csv",
    )


run()
