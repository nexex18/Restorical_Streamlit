import streamlit as st
import json
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Site Detail", page_icon="🧭", layout="wide")


@st.cache_data(ttl=3600)  # Cache for 1 hour
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

    # Get the final score for this site
    import json
    score_df = query_df(
        """
        WITH lr AS (
            SELECT or1.run_id, or1.final_score AS run_final_score, or1.completed_at
            FROM orchestration_runs or1
            WHERE or1.site_id = ? AND or1.completed_at IS NOT NULL
            ORDER BY or1.completed_at DESC
            LIMIT 1
        )
        SELECT lr.run_final_score, omr.module_result_json
        FROM lr
        LEFT JOIN orchestration_module_results omr
            ON omr.run_id = lr.run_id AND omr.module_name LIKE '%Score Calculation%'
        """,
        [site_id],
    )

    final_score = None
    if not score_df.empty:
        score_row = score_df.iloc[0]
        try:
            if score_row.module_result_json:
                data = json.loads(score_row.module_result_json)
                final_score = int((data.get('data') or {}).get('final_score') or 0)
        except Exception:
            pass
        if final_score is None:
            final_score = int(score_row.run_final_score or 0)

    # External link to WA Ecology site if available
    site_url = row.get("url") or row.get("site_report_url") or row.get("neighborhood_map_url")
    if site_url:
        st.markdown(
            f"<a href='{site_url}' target='_blank' rel='noopener noreferrer'>Open on WA Ecology site ↗</a>",
            unsafe_allow_html=True,
        )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Score", final_score if final_score is not None else "N/A")
    c2.metric("Documents", int(row.get("total_documents") or 0))
    c3.metric("Contaminants", int(row.get("total_contaminants") or 0))
    c4.metric("Has Docs", "✅" if row.get("has_documents") else "❌")
    c5.metric("Has Narratives", "✅" if row.get("found_documents") else "❌")
    c6.metric("Scrape Status", row.get("scrape_status") or "–")

    st.write("""
    Quick Links:
    """)
    st.page_link("pages/03_Sites_Explorer.py", label="Open Sites Explorer", icon="🌐")
    st.page_link("pages/04_Narratives.py", label="Narratives Page", icon="📜")
    st.page_link("pages/05_Documents.py", label="Documents Page", icon="📄")
    st.page_link("pages/06_Feedback.py", label="Feedback Page", icon="💬")
    st.page_link("pages/08_Contaminants.py", label="Contaminants Page", icon="🧪")
    st.page_link("pages/09_Contacts.py", label="Contacts Page", icon="📇")

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

    # Show only the overall score
    st.metric("Overall Score", f"{overall_score}")

    # Parse evidence JSON from the most recent qualification row + confidence from summary
    # Check if final_recommendation column exists
    check_col = query_df(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='site_summary'"
    )
    has_final_recommendation = False
    if not check_col.empty:
        table_sql = check_col.iloc[0]['sql']
        has_final_recommendation = 'final_recommendation' in table_sql

    # Build query based on available columns
    if has_final_recommendation:
        ev = query_df(
            """
            SELECT
              sqr.age_evidence,
              sqr.third_party_evidence,
              sqr.qualified,
              sqr.disqualifying_factors,
              sqr.age_qualified,
              sqr.third_party_qualified,
              ss.age_evidence_confidence_score,
              ss.third_party_confidence_score,
              ss.age_evidence_source,
              ss.final_recommendation
            FROM site_qualification_results sqr
            LEFT JOIN site_summary ss ON ss.site_id = sqr.site_id
            WHERE sqr.site_id = ?
            ORDER BY sqr.analyzed_at DESC
            LIMIT 1
            """,
            [site_id],
        )
    else:
        ev = query_df(
            """
            SELECT
              sqr.age_evidence,
              sqr.third_party_evidence,
              sqr.qualified,
              sqr.disqualifying_factors,
              sqr.age_qualified,
              sqr.third_party_qualified,
              ss.age_evidence_confidence_score,
              ss.third_party_confidence_score,
              ss.age_evidence_source,
              NULL as final_recommendation
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
    is_minimal_cleanup = False
    minimal_cleanup_reasons = []
    disqualifying_factors = []

    if not ev.empty:
        r = ev.iloc[0]

        # Parse disqualifying_factors JSON if present
        if hasattr(r, 'disqualifying_factors') and r.disqualifying_factors:
            try:
                disqualifying_factors = json.loads(r.disqualifying_factors)
                # Check if any factor is MINIMAL_CLEANUP
                for factor in disqualifying_factors:
                    if factor.get('reason') == 'MINIMAL_CLEANUP':
                        is_minimal_cleanup = True
                        if factor.get('evidence'):
                            minimal_cleanup_reasons.append(factor.get('evidence'))
            except Exception:
                disqualifying_factors = []

        # Check for minimal cleanup disqualification (legacy check)
        if r.final_recommendation == "DISQUALIFIED_MINIMAL_CLEANUP":
            is_minimal_cleanup = True

        try:
            age_items = json.loads(r.age_evidence) if r.age_evidence else []
        except Exception:
            age_items = []
        try:
            tp_items = json.loads(r.third_party_evidence) if r.third_party_evidence else []
        except Exception:
            tp_items = []

        # Check for disqualified evidence items
        for item in age_items + tp_items:
            if isinstance(item, dict):
                evidence_text = str(item.get('evidence_text', ''))
                confidence = item.get('confidence_level', '')
                if '[DISQUALIFIED - MINIMAL CLEANUP]' in evidence_text or confidence == 'disqualified':
                    is_minimal_cleanup = True
                    # Extract the reason from the evidence text
                    if 'minimal' in evidence_text.lower() or 'cleanup' in evidence_text.lower():
                        clean_text = evidence_text.replace('[DISQUALIFIED - MINIMAL CLEANUP]', '').strip()
                        if clean_text and clean_text not in minimal_cleanup_reasons:
                            minimal_cleanup_reasons.append(clean_text)

        age_conf = int(r.age_evidence_confidence_score or 0)
        tp_conf = int(r.third_party_confidence_score or 0)
        age_src = r.age_evidence_source

    # Display qualification summary box if we have the data
    if not ev.empty and hasattr(r, 'age_qualified') and hasattr(r, 'third_party_qualified'):
        age_qual_status = r.age_qualified
        tp_qual_status = r.third_party_qualified
        overall_qual_status = r.qualified if hasattr(r, 'qualified') else False

        # Create qualification status summary
        with st.container():
            st.subheader("📋 Qualification Summary")
            col1, col2, col3 = st.columns(3)

            # Age qualification status
            age_icon = "✅" if age_qual_status else "❌"
            age_text = "PASSED" if age_qual_status else "FAILED"
            col1.markdown(f"**Age Qualification:** {age_icon} {age_text}")

            # Third-party qualification status
            tp_icon = "✅" if tp_qual_status else "❌"
            tp_text = "PASSED" if tp_qual_status else "FAILED"
            col2.markdown(f"**Third-Party:** {tp_icon} {tp_text}")

            # Overall qualification
            overall_icon = "✅" if overall_qual_status else "❌"
            overall_text = "QUALIFIED" if overall_qual_status else "NOT QUALIFIED"
            col3.markdown(f"**Overall:** {overall_icon} {overall_text}")

            st.divider()

    # Display disqualification details prominently at the top
    if disqualifying_factors:
        for factor in disqualifying_factors:
            category = factor.get('category', 'unknown')
            reason = factor.get('reason', '')
            description = factor.get('description', '')
            evidence = factor.get('evidence', '')

            # Determine the alert type and icon based on reason
            if reason == 'MINIMAL_CLEANUP':
                st.error("🚫 **Site Disqualified: Minimal Cleanup/Recovery**")
                st.markdown(f"**Category:** {category.title()} Qualification")
                st.markdown(f"**Reason:** {description}")
                if evidence:
                    with st.expander("📄 View Supporting Evidence"):
                        st.info(f'"{evidence}"')
            elif reason == 'RECENT_CONTAMINATION':
                st.error("🚫 **Site Disqualified: Recent Contamination**")
                st.markdown(f"**Category:** {category.title()} Qualification")
                st.markdown(f"**Reason:** {description}")
                if evidence:
                    with st.expander("📄 View Supporting Evidence"):
                        st.info(f'"{evidence}"')
            elif reason == 'NO_THIRD_PARTY_IMPACT':
                st.error("🚫 **Site Disqualified: No Third Party Impact**")
                st.markdown(f"**Category:** {category.title()} Qualification")
                st.markdown(f"**Reason:** {description}")
                if evidence:
                    with st.expander("📄 View Supporting Evidence"):
                        st.info(f'"{evidence}"')
            else:
                st.warning(f"⚠️ **Site Disqualified**")
                st.markdown(f"**Category:** {category.title()} Qualification")
                st.markdown(f"**Reason:** {description or reason}")
                if evidence:
                    with st.expander("📄 View Supporting Evidence"):
                        st.info(f'"{evidence}"')

        # Add a divider after disqualification details
        st.divider()

    # Legacy display for sites without new disqualifying_factors field
    elif is_minimal_cleanup:
        st.warning("⚠️ **Site Disqualified: Minimal Cleanup/Recovery**\n\n"
                   "This site has been disqualified because the evidence indicates minimal contamination "
                   "or cleanup/recovery work required. There may be insufficient damages to pursue.")
        if minimal_cleanup_reasons:
            with st.expander("View Disqualification Details"):
                for reason in minimal_cleanup_reasons[:3]:  # Show top 3 reasons
                    st.write(f"• {reason}")

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
            evidence_text = item.get('evidence_text', '')
            confidence = item.get('confidence_level', '')
            is_disqualified = '[DISQUALIFIED - MINIMAL CLEANUP]' in str(evidence_text) or confidence == 'disqualified'

            # Clean the evidence text
            txt = _clean_evidence(evidence_text)
            if txt:
                age_items_clean.append({
                    'text': txt,
                    'source_document': item.get('source_document'),
                    'document_date': item.get('document_date'),
                    'document_type': item.get('document_type'),
                    'is_disqualified': is_disqualified
                })
        elif isinstance(item, str):
            txt = _clean_evidence(item)
            if txt:
                age_items_clean.append({'text': txt, 'source_document': None, 'document_date': None, 'document_type': None, 'is_disqualified': False})
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

            # Add disqualified marker to header if needed
            disqualified_marker = " ❌ [DISQUALIFIED - MINIMAL CLEANUP]" if it.get('is_disqualified') else ""
            header = f"Source: Narrative{disqualified_marker}" if src_label == 'Narrative' else (
                f"Source: Document — [{title}]({url}){disqualified_marker}" if url else f"Source: Document — {title}{disqualified_marker}"
            )
            with st.expander(header, expanded=not it.get('is_disqualified')):
                if it.get('is_disqualified'):
                    st.error("⚠️ This evidence was disqualified due to minimal cleanup/contamination")
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
            evidence_text = item.get('evidence_text', '')
            confidence = item.get('confidence_level', '')
            is_disqualified = '[DISQUALIFIED - MINIMAL CLEANUP]' in str(evidence_text) or confidence == 'disqualified'

            # Clean the evidence text
            txt = _clean_evidence(evidence_text)
            if txt:
                tp_items_clean.append({
                    'text': txt,
                    'source_document': item.get('source_document'),
                    'document_date': item.get('document_date'),
                    'document_type': item.get('document_type'),
                    'is_disqualified': is_disqualified
                })
        elif isinstance(item, str):
            txt = _clean_evidence(item)
            if txt:
                tp_items_clean.append({'text': txt, 'source_document': None, 'document_date': None, 'document_type': None, 'is_disqualified': False})
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

            # Add disqualified marker to header if needed
            disqualified_marker = " ❌ [DISQUALIFIED - MINIMAL CLEANUP]" if it.get('is_disqualified') else ""
            if url:
                header = f"Source: Document — [{title}]({url}){disqualified_marker}"
            elif title:
                header = f"Source: Document — {title}{disqualified_marker}"
            else:
                header = f"Source: Narrative{disqualified_marker}"
            with st.expander(header, expanded=not it.get('is_disqualified')):
                if it.get('is_disqualified'):
                    st.error("⚠️ This evidence was disqualified due to minimal cleanup/contamination")
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
               confidence_score, site_url
        FROM site_contacts_summary
        WHERE site_id = ?
        ORDER BY prospect_priority ASC, confidence_score DESC
        LIMIT 2000
        """,
        [site_id],
    )
    st.write(f"Contacts: {len(df):,}")
    st.dataframe(df, use_container_width=True, height=500)


def ownership_history_tab(site_id: str):
    st.subheader("Ownership History")

    # Get ownership history from database
    df = query_df(
        """
        SELECT
            ownership_start_year,
            ownership_end_year,
            ownership_duration_years,
            owner_name,
            organization_name,
            is_current,
            acquired_from,
            sold_to,
            acquisition_type,
            business_name,
            business_type,
            operated_business,
            operation_start_year,
            operation_end_year,
            parent_company,
            successor_company,
            assumes_prior_liabilities
        FROM site_ownership_history
        WHERE site_id = ?
        ORDER BY COALESCE(ownership_start_year, 9999), ownership_start_date
        """,
        [site_id],
    )

    if df.empty:
        st.info("No ownership history available for this site.")
        return

    st.write(f"Total ownership records: {len(df):,}")

    # Create timeline visualization
    st.markdown("### Ownership Timeline")

    for idx, row in df.iterrows():
        # Determine ownership period
        start_year = row.get('ownership_start_year', 'Unknown')
        end_year = row.get('ownership_end_year', 'Present' if row.get('is_current') else 'Unknown')
        duration = row.get('ownership_duration_years', '')

        # Create expandable card for each ownership period
        with st.expander(f"📅 {start_year} - {end_year}: {row.get('owner_name', 'Unknown Owner')}" +
                        (f" (Current)" if row.get('is_current') else "")):

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Owner Information**")
                st.write(f"• **Name:** {row.get('owner_name', 'N/A')}")
                if row.get('organization_name'):
                    st.write(f"• **Organization:** {row.get('organization_name')}")
                if row.get('parent_company'):
                    st.write(f"• **Parent Company:** {row.get('parent_company')}")
                if duration:
                    st.write(f"• **Duration:** {duration} years")

                st.markdown("**Transfer Information**")
                if row.get('acquired_from'):
                    st.write(f"• **Acquired From:** {row.get('acquired_from')}")
                if row.get('acquisition_type'):
                    st.write(f"• **Acquisition Type:** {row.get('acquisition_type')}")
                if row.get('sold_to'):
                    st.write(f"• **Sold To:** {row.get('sold_to')}")
                if row.get('successor_company'):
                    st.write(f"• **Successor Company:** {row.get('successor_company')}")

            with col2:
                st.markdown("**Business Operations**")
                if row.get('operated_business'):
                    st.write("• **Operated Business:** Yes")
                    if row.get('business_name'):
                        st.write(f"• **Business Name:** {row.get('business_name')}")
                    if row.get('business_type'):
                        st.write(f"• **Business Type:** {row.get('business_type')}")
                    if row.get('operation_start_year') or row.get('operation_end_year'):
                        op_start = row.get('operation_start_year', 'Unknown')
                        op_end = row.get('operation_end_year', 'Unknown')
                        st.write(f"• **Operation Period:** {op_start} - {op_end}")
                else:
                    st.write("• **Operated Business:** No")

                if row.get('assumes_prior_liabilities') is not None:
                    liability_status = "Yes" if row.get('assumes_prior_liabilities') else "No"
                    st.write(f"• **Assumes Prior Liabilities:** {liability_status}")

    # Display raw data table
    st.markdown("### Full Ownership Data")
    st.dataframe(df, use_container_width=True, height=400)


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

    tabs = st.tabs(["Overview", "Narratives", "Documents", "Qualifications", "Contaminants", "Contacts", "Ownership History"])

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
    with tabs[6]:
        ownership_history_tab(site_id)


run()
