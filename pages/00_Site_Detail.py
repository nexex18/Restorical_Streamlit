import streamlit as st
import json
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Site Detail", page_icon="🧭", layout="wide")


def site_options():
    df = query_df(
        """
        SELECT s.site_id,
               COALESCE(ss.site_name,'') AS site_name,
               COALESCE(ss.site_address,'') AS site_address
        FROM sites s
        LEFT JOIN site_summary ss ON s.site_id = ss.site_id
        ORDER BY CAST(s.site_id AS INTEGER)
        LIMIT 10000
        """
    )
    opts = []
    for _, r in df.iterrows():
        label = f"{r.site_id} — {r.site_name}" if r.site_name else str(r.site_id)
        opts.append((label, r.site_id))
    return opts


def overview_tab(site_id: str):
    st.subheader("Overview")
    ov = query_df(
        """
        SELECT *
        FROM site_overview
        WHERE site_id = ?
        """,
        [site_id],
    )
    if ov.empty:
        st.info("No overview record for this site.")
        return

    row = ov.iloc[0]
    # External link to WA Ecology site if available
    site_url = row.get("url") or row.get("site_report_url") or row.get("neighborhood_map_url")
    if site_url:
        st.markdown(
            f"<a href='{site_url}' target='_blank' rel='noopener noreferrer'>Open on WA Ecology site ↗</a>",
            unsafe_allow_html=True,
        )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Documents", int(row.get("total_documents") or 0))
    c2.metric("Contaminants", int(row.get("total_contaminants") or 0))
    c3.metric("Has Docs", "✅" if row.get("has_documents") else "❌")
    c4.metric("Has Narratives", "✅" if row.get("found_documents") else "❌")
    c5.metric("Scrape Status", row.get("scrape_status") or "–")

    st.write("""
    Quick Links:
    """)
    st.page_link("pages/02_Sites_Explorer.py", label="Open Sites Explorer", icon="🌐")
    st.page_link("pages/03_Narratives.py", label="Narratives Page", icon="📜")
    st.page_link("pages/04_Documents.py", label="Documents Page", icon="📄")
    st.page_link("pages/05_Qualifications.py", label="Qualifications Page", icon="✅")
    st.page_link("pages/06_Contaminants.py", label="Contaminants Page", icon="🧪")
    st.page_link("pages/07_Contacts.py", label="Contacts Page", icon="📇")

    st.markdown("---")
    meta_cols = st.columns(2)
    with meta_cols[0]:
        st.write({
            "site_id": row.get("site_id"),
            "site_name": row.get("site_name"),
            "site_address": row.get("site_address"),
            "regional_office": row.get("regional_office"),
            "office_phone": row.get("office_phone"),
            "cleanup_program_type": row.get("cleanup_program_type"),
        })
    with meta_cols[1]:
        st.write({
            "site_report_url": row.get("site_report_url"),
            "neighborhood_map_url": row.get("neighborhood_map_url"),
            "url": row.get("url"),
        })


def narratives_tab(site_id: str):
    st.subheader("Narratives")
    df = query_df(
        """
        SELECT section_order, section_title, section_content, scraped_at
        FROM site_narratives
        WHERE site_id = ?
        ORDER BY section_order, scraped_at
        """,
        [site_id],
    )
    if df.empty:
        st.info("No narratives available for this site.")
        return
    for _, row in df.iterrows():
        st.markdown(f"### {int(row.section_order)} — {row.section_title}")
        with st.expander("View content", expanded=False):
            st.write(row.section_content)


def documents_tab(site_id: str):
    st.subheader("Documents")
    df = query_df(
        """
        SELECT id, document_category, document_title, document_date, document_type,
               document_url, download_status, flagged_for_analysis, file_extension, file_size_bytes
        FROM site_documents
        WHERE site_id = ?
        ORDER BY 
          CASE WHEN download_status = 'success' THEN 0 ELSE 1 END ASC,
          id DESC
        LIMIT 2000
        """,
        [site_id],
    )
    st.write(f"Documents: {len(df):,}")

    # Reorder columns so flagged_for_analysis is 4th and download_status is 5th
    if not df.empty:
        df = df.copy()
        # Ensure flagged shows as 0/1 (not checkbox)
        if "flagged_for_analysis" in df.columns:
            try:
                df["flagged_for_analysis"] = df["flagged_for_analysis"].fillna(0).astype(int)
            except Exception:
                pass

        preferred_order = [
            "id",
            "document_category",
            "document_title",
            "flagged_for_analysis",  # 4th column
            "download_status",       # 5th column (next to flagged)
            "document_date",
            "document_type",
            "document_url",          # make URL clickable
            "file_extension",
            "file_size_bytes",
        ]
        cols = [c for c in preferred_order if c in df.columns] + [c for c in df.columns if c not in preferred_order]
        df = df[cols]

    # Render table with clickable Document Title and no raw URL
    if not df.empty:
        import html as _html
        cols = [
            ("id", "ID"),
            ("document_category", "Category"),
            ("document_title", "Document Title"),
            ("flagged_for_analysis", "Flagged"),
            ("download_status", "Download Status"),
            ("document_date", "Date"),
            ("document_type", "Type"),
            ("file_extension", "Ext"),
            ("file_size_bytes", "Size (bytes)"),
        ]
        headers = ''.join(f'<th style="text-align:left;padding:6px 10px;">{label}</th>' for _, label in cols)
        rows_html = []
        for _, r in df.iterrows():
            url = str(r.get("document_url") or "").strip()
            title = _html.escape(str(r.get("document_title") or ""))
            title_html = title if not url else f'<a href="{_html.escape(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
            vals = [
                r.get("id"),
                r.get("document_category"),
                title_html,
                r.get("flagged_for_analysis"),
                r.get("download_status"),
                r.get("document_date"),
                r.get("document_type"),
                r.get("file_extension"),
                r.get("file_size_bytes"),
            ]
            tds = []
            for i, v in enumerate(vals):
                if i == 2:  # title_html already escaped/linked
                    tds.append(f'<td style="padding:6px 10px;">{v}</td>')
                else:
                    tds.append(f'<td style="padding:6px 10px;">{_html.escape(str(v)) if v is not None else ""}</td>')
            rows_html.append('<tr>' + ''.join(tds) + '</tr>')
        table_html = f"""
        <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr>{headers}</tr></thead>
          <tbody>
            {''.join(rows_html)}
          </tbody>
        </table>
        </div>
        """
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("No documents found for this site.")


def qualifications_tab(site_id: str):
    st.subheader("Qualifications")

    # Helper: clean evidence fragments that may include wrappers like "[{:" etc.
    def _clean_evidence(txt: str) -> str:
        if txt is None:
            return ""
        s = str(txt)
        if ':' in s:
            s = s.split(':', 1)[1]
        cut_points = [i for i in (s.find(']'), s.find('}')) if i != -1]
        if cut_points:
            s = s[:min(cut_points)]
        return s.strip().strip('\"\'')

    # Overall run and scoring (Module 10 Score Calculation)
    run_df = query_df(
        """
        SELECT run_id, started_at, completed_at, final_status, final_score, total_processing_time_seconds
        FROM orchestration_runs
        WHERE site_id = ? AND completed_at IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        [site_id],
    )
    overall_tier = "UNSPECIFIED"
    overall_score = 0
    module10_data = {}
    if not run_df.empty:
        run = run_df.iloc[0]
        # Derive tier from final_status
        fs = str(run.final_status or '')
        if 'QUALIFIED_TIER_' in fs:
            overall_tier = fs.replace('QUALIFIED_TIER_', '')
        elif 'NOT_QUALIFIED' in fs:
            overall_tier = 'NOT_QUALIFIED'
        # Try to read module 10 result
        mod_df = query_df(
            """
            SELECT module_result_json
            FROM orchestration_module_results
            WHERE run_id = ? AND module_name LIKE '%Score Calculation%'
            LIMIT 1
            """,
            [run.run_id],
        )
        if not mod_df.empty and mod_df.iloc[0].module_result_json:
            try:
                data = json.loads(mod_df.iloc[0].module_result_json)
                d = data.get('data') or {}
                module10_data = d
                overall_score = int(d.get('final_score') or run.final_score or 0)
            except Exception:
                overall_score = int(run.final_score or 0)
        else:
            overall_score = int(run.final_score or 0)

    c1, c2 = st.columns(2)
    c1.metric("Overall Tier", overall_tier)
    c2.metric("Overall Score", f"{overall_score}")

    # Parse evidence JSON from the most recent qualification row + confidence from summary
    ev = query_df(
        """
        SELECT 
          sqr.age_evidence,
          sqr.third_party_evidence,
          ss.age_evidence_confidence_score,
          ss.third_party_confidence_score,
          ss.age_evidence_source
        FROM site_qualification_results sqr
        LEFT JOIN site_summary ss ON ss.site_id = sqr.site_id
        WHERE sqr.site_id = ?
        ORDER BY sqr.analyzed_at DESC
        LIMIT 1
        """,
        [site_id],
    )
    age_items, tp_items = [], []
    age_conf = 0
    tp_conf = 0
    age_src = None
    if not ev.empty:
        r = ev.iloc[0]
        try:
            age_items = json.loads(r.age_evidence) if r.age_evidence else []
        except Exception:
            age_items = []
        try:
            tp_items = json.loads(r.third_party_evidence) if r.third_party_evidence else []
        except Exception:
            tp_items = []
        age_conf = int(r.age_evidence_confidence_score or 0)
        tp_conf = int(r.third_party_confidence_score or 0)
        age_src = r.age_evidence_source

    # Build a mapping of document title -> URL for linking
    docs = query_df(
        """
        SELECT document_title, document_url, document_date, document_type
        FROM site_documents
        WHERE site_id = ?
        """,
        [site_id],
    )
    title_to_url = {}
    if not docs.empty:
        for _, row in docs.iloc[::-1].iterrows():
            t = str(row.document_title or '').strip()
            if t and t not in title_to_url:
                title_to_url[t] = row.document_url

    # Age Evidence section (only non-empty evidence)
    age_items_clean = []
    for item in age_items:
        if isinstance(item, dict):
            txt = _clean_evidence(item.get('evidence_text'))
            if txt:
                age_items_clean.append({
                    'text': txt,
                    'source_document': item.get('source_document'),
                    'document_date': item.get('document_date'),
                    'document_type': item.get('document_type'),
                })
        elif isinstance(item, str):
            txt = _clean_evidence(item)
            if txt:
                age_items_clean.append({'text': txt, 'source_document': None, 'document_date': None, 'document_type': None})
    # Fallback if DB stored plain text instead of JSON list
    if not age_items_clean and ev is not None and not ev.empty:
        raw = ev.iloc[0].get('age_evidence')
        if isinstance(raw, str):
            txt = _clean_evidence(raw)
            if txt:
                age_items_clean.append({'text': txt, 'source_document': None, 'document_date': None, 'document_type': None})
    if age_items_clean:
        pts = module10_data.get('age_score') if isinstance(module10_data, dict) else None
        pts_str = f" ({pts} points)" if isinstance(pts, (int, float)) else ""
        st.subheader(f"Age Evidence{pts_str}{f' (Confidence: {age_conf}%)' if age_conf else ''}")
        src_label = 'Narrative' if age_src == 'narrative_analysis' else 'Document'
        st.caption(f"Evidence Source: {src_label}")
        for it in age_items_clean:
            title = it.get('source_document') or 'Document'
            url = title_to_url.get(str(title).strip())
            header = f"Source: Narrative" if src_label == 'Narrative' else (
                f"Source: Document — [{title}]({url})" if url else f"Source: Document — {title}"
            )
            with st.expander(header, expanded=True):
                st.write(it['text'])
                if src_label != 'Narrative':
                    meta = []
                    if it.get('document_date'): meta.append(str(it['document_date']))
                    if it.get('document_type'): meta.append(str(it['document_type']))
                    if meta:
                        st.caption(" | ".join(meta))

    # Third-Party Evidence section (only non-empty evidence)
    tp_items_clean = []
    for item in tp_items:
        if isinstance(item, dict):
            txt = _clean_evidence(item.get('evidence_text'))
            if txt:
                tp_items_clean.append({
                    'text': txt,
                    'source_document': item.get('source_document'),
                    'document_date': item.get('document_date'),
                    'document_type': item.get('document_type'),
                })
        elif isinstance(item, str):
            txt = _clean_evidence(item)
            if txt:
                tp_items_clean.append({'text': txt, 'source_document': None, 'document_date': None, 'document_type': None})
    # Fallback if DB stored plain text instead of JSON list
    if not tp_items_clean and ev is not None and not ev.empty:
        raw = ev.iloc[0].get('third_party_evidence')
        if isinstance(raw, str):
            txt = _clean_evidence(raw)
            if txt:
                tp_items_clean.append({'text': txt, 'source_document': None, 'document_date': None, 'document_type': None})
    if tp_items_clean:
        pts = module10_data.get('third_party_score') if isinstance(module10_data, dict) else None
        pts_str = f" ({pts} points)" if isinstance(pts, (int, float)) else ""
        st.subheader(f"3rd Party Evidence{pts_str}{f' (Confidence: {tp_conf}%)' if tp_conf else ''}")

        # Include contamination status summary (C/S/B) to mirror V3 guidance
        cont = query_df(
            """
            SELECT contaminant_type,
                   soil_status,
                   groundwater_status,
                   surface_water_status,
                   sediment_status
            FROM site_contaminants
            WHERE site_id = ?
              AND (
                soil_status IN ('S','C','B') OR
                groundwater_status IN ('S','C','B') OR
                surface_water_status IN ('S','C','B') OR
                sediment_status IN ('S','C','B')
              )
            ORDER BY 
              CASE 
                WHEN groundwater_status IN ('C','S') THEN 1
                WHEN soil_status IN ('C','S') THEN 2
                WHEN surface_water_status IN ('C','S') THEN 3
                ELSE 4
              END
            LIMIT 10
            """,
            [site_id],
        )
        if not cont.empty:
            st.caption("Contamination Status (C=Confirmed, S=Suspected, B=Below Levels)")
            st.dataframe(cont, use_container_width=True, height=240)

        for it in tp_items_clean:
            title = (it.get('source_document') or '').strip() if isinstance(it.get('source_document'), str) else ''
            url = title_to_url.get(title) if title else None
            if url:
                header = f"Source: Document — [{title}]({url})"
            elif title:
                header = f"Source: Document — {title}"
            else:
                header = "Source: Narrative"
            with st.expander(header, expanded=True):
                st.write(it['text'])
                meta = []
                if it.get('document_date'): meta.append(str(it['document_date']))
                if it.get('document_type'): meta.append(str(it['document_type']))
                if meta:
                    st.caption(" | ".join(meta))


def contaminants_tab(site_id: str):
    st.subheader("Contaminants")
    df = query_df(
        """
        SELECT contaminant_type, soil_status, groundwater_status, surface_water_status,
               air_status, sediment_status, bedrock_status
        FROM site_contaminants
        WHERE site_id = ?
        ORDER BY contaminant_type
        LIMIT 2000
        """,
        [site_id],
    )
    st.write(f"Rows: {len(df):,}")
    st.dataframe(df, use_container_width=True, height=500)


def contacts_tab(site_id: str):
    st.subheader("Contacts")
    df = query_df(
        """
        SELECT contact_name, organization_name, contact_address, phone, email,
               contact_type, contact_role, is_primary_prospect, prospect_priority,
               confidence_score, qualification_tier, qualified, site_url
        FROM site_contacts_summary
        WHERE site_id = ?
        ORDER BY prospect_priority ASC, confidence_score DESC
        LIMIT 2000
        """,
        [site_id],
    )
    st.write(f"Contacts: {len(df):,}")
    st.dataframe(df, use_container_width=True, height=500)


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Site Detail 🧭")
    st.caption("A single-page deep-dive into a site: overview, narratives, documents, qualifications, contaminants, and contacts.")

    opts = site_options()
    if not opts:
        st.info("No sites found.")
        st.stop()

    labels = [label for label, _ in opts]
    label_to_id = {label: sid for label, sid in opts}
    # Try to read site_id from query params for deep-link support
    qp_site_id = None
    try:
        qp_site_id = st.query_params.get("site_id")
    except Exception:
        try:
            qpexp = st.experimental_get_query_params()
            v = qpexp.get("site_id")
            qp_site_id = v[0] if isinstance(v, list) else v
        except Exception:
            qp_site_id = None

    # Compute default index based on query param if present
    id_list = [sid for _, sid in opts]
    default_index = 0
    if qp_site_id is not None:
        qp_site_id_str = str(qp_site_id)
        for i, sid in enumerate(id_list):
            if str(sid) == qp_site_id_str:
                default_index = i
                break

    selected_label = st.selectbox("Select Site", labels, index=default_index)
    site_id = label_to_id[selected_label]

    # Persist selected site to query params to keep URL shareable
    try:
        st.query_params["site_id"] = str(site_id)
    except Exception:
        try:
            st.experimental_set_query_params(site_id=str(site_id))
        except Exception:
            pass

    tabs = st.tabs(["Overview", "Narratives", "Documents", "Qualifications", "Contaminants", "Contacts"])

    with tabs[0]:
        overview_tab(site_id)
    with tabs[1]:
        narratives_tab(site_id)
    with tabs[2]:
        documents_tab(site_id)
    with tabs[3]:
        qualifications_tab(site_id)
    with tabs[4]:
        contaminants_tab(site_id)
    with tabs[5]:
        contacts_tab(site_id)


run()
