import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Contacts", page_icon="📇", layout="wide")


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
    tier_opts = query_df("SELECT DISTINCT COALESCE(qualification_tier,'UNSPECIFIED') AS v FROM site_contacts_summary ORDER BY v")

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
    with c4:
        tiers_sel = st.multiselect("Qualification Tier", tier_opts["v"].tolist() if not tier_opts.empty else [], default=[])

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

    if tiers_sel:
        placeholders = ",".join(["?"] * len(tiers_sel))
        # Match UNSPECIFIED to NULL as well
        if "UNSPECIFIED" in tiers_sel:
            # Include rows where qualification_tier IS NULL
            non_unspec = [t for t in tiers_sel if t != "UNSPECIFIED"]
            if non_unspec:
                placeholders_non = ",".join(["?"] * len(non_unspec))
                where.append(f"(qualification_tier IN ({placeholders_non}) OR qualification_tier IS NULL)")
                params += non_unspec
            else:
                where.append("qualification_tier IS NULL")
        else:
            where.append(f"qualification_tier IN ({placeholders})")
            params += tiers_sel

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
               qualification_tier, qualified, site_url
        FROM site_contacts_summary
        {where_sql}
        ORDER BY CAST(site_id AS INTEGER), prospect_priority ASC, confidence_score DESC
        LIMIT 10000
        """,
        params,
    )

    st.write(f"Results: {len(df):,}")
    st.dataframe(df, use_container_width=True, height=700)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="contacts_export.csv",
        mime="text/csv",
    )


run()
