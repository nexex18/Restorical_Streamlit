import streamlit as st
from app_lib.db import query_df, db_exists
import pandas as pd
import json
import os

st.set_page_config(page_title="Feedback", page_icon="📝", layout="wide")

# URL prefix for deployment behind nginx (e.g., '/streamlit')
URL_PREFIX = os.environ.get('URL_PREFIX', '')

def run():
    if not db_exists():
        st.error("Database not found")
        st.stop()

    st.title("User Feedback 📝")
    st.caption("Review feedback provided on AI qualification analyses")
    
    # Get sites with feedback - first check what columns exist
    try:
        # Try with score columns if they exist
        feedback_summary = query_df("""
            WITH latest_scores AS (
                SELECT 
                    af.site_id,
                    af.age_score,
                    af.third_party_score,
                    ROW_NUMBER() OVER (PARTITION BY af.site_id ORDER BY af.submitted_at DESC) as rn
                FROM ai_feedback af
            ),
            latest_age_feedback AS (
                SELECT 
                    af.site_id,
                    af.age_correct,
                    ROW_NUMBER() OVER (PARTITION BY af.site_id ORDER BY af.submitted_at DESC) as rn
                FROM ai_feedback af
                WHERE af.age_correct IS NOT NULL
            ),
            latest_tp_feedback AS (
                SELECT 
                    af.site_id,
                    af.third_party_correct,
                    ROW_NUMBER() OVER (PARTITION BY af.site_id ORDER BY af.submitted_at DESC) as rn
                FROM ai_feedback af
                WHERE af.third_party_correct IS NOT NULL
            )
            SELECT 
                af.site_id,
                so.site_name,
                so.site_address,
                COUNT(DISTINCT af.run_id) as feedback_count,
                MAX(af.submitted_at) as latest_feedback,
                SUM(CASE WHEN af.age_correct = 1 THEN 1 ELSE 0 END) as age_correct_count,
                SUM(CASE WHEN af.third_party_correct = 1 THEN 1 ELSE 0 END) as third_party_correct_count,
                SUM(CASE WHEN af.document_selection_correct = 1 THEN 1 ELSE 0 END) as doc_correct_count,
                -- Get the latest scores (even if null)
                MAX(ls.age_score) as age_score,
                MAX(ls.third_party_score) as third_party_score,
                -- Get the latest non-null feedback values
                MAX(laf.age_correct) as latest_age_correct,
                MAX(ltf.third_party_correct) as latest_third_party_correct
            FROM ai_feedback af
            LEFT JOIN site_overview so ON af.site_id = so.site_id
            LEFT JOIN latest_scores ls ON af.site_id = ls.site_id AND ls.rn = 1
            LEFT JOIN latest_age_feedback laf ON af.site_id = laf.site_id AND laf.rn = 1
            LEFT JOIN latest_tp_feedback ltf ON af.site_id = ltf.site_id AND ltf.rn = 1
            GROUP BY af.site_id, so.site_name, so.site_address
            ORDER BY latest_feedback DESC
        """)
    except:
        # Fallback if score columns don't exist - get scores from orchestration runs
        feedback_summary = query_df("""
            WITH latest_run AS (
                SELECT 
                    af.site_id,
                    af.run_id,
                    ROW_NUMBER() OVER (PARTITION BY af.site_id ORDER BY af.submitted_at DESC) as rn
                FROM ai_feedback af
            ),
            latest_age_feedback AS (
                SELECT 
                    af.site_id,
                    af.age_correct,
                    ROW_NUMBER() OVER (PARTITION BY af.site_id ORDER BY af.submitted_at DESC) as rn
                FROM ai_feedback af
                WHERE af.age_correct IS NOT NULL
            ),
            latest_tp_feedback AS (
                SELECT 
                    af.site_id,
                    af.third_party_correct,
                    ROW_NUMBER() OVER (PARTITION BY af.site_id ORDER BY af.submitted_at DESC) as rn
                FROM ai_feedback af
                WHERE af.third_party_correct IS NOT NULL
            )
            SELECT 
                af.site_id,
                so.site_name,
                so.site_address,
                COUNT(DISTINCT af.run_id) as feedback_count,
                MAX(af.submitted_at) as latest_feedback,
                SUM(CASE WHEN af.age_correct = 1 THEN 1 ELSE 0 END) as age_correct_count,
                SUM(CASE WHEN af.third_party_correct = 1 THEN 1 ELSE 0 END) as third_party_correct_count,
                SUM(CASE WHEN af.document_selection_correct = 1 THEN 1 ELSE 0 END) as doc_correct_count,
                -- Get scores from the most recent feedback's run
                MAX(CASE WHEN lr.rn = 1 THEN scores.age_score END) as age_score,
                MAX(CASE WHEN lr.rn = 1 THEN scores.third_party_score END) as third_party_score,
                -- Get the latest non-null feedback values
                MAX(laf.age_correct) as latest_age_correct,
                MAX(ltf.third_party_correct) as latest_third_party_correct
            FROM ai_feedback af
            LEFT JOIN site_overview so ON af.site_id = so.site_id
            LEFT JOIN latest_run lr ON af.site_id = lr.site_id AND lr.rn = 1
            LEFT JOIN latest_age_feedback laf ON af.site_id = laf.site_id AND laf.rn = 1
            LEFT JOIN latest_tp_feedback ltf ON af.site_id = ltf.site_id AND ltf.rn = 1
            LEFT JOIN (
                -- Extract scores from orchestration module results
                SELECT 
                    omr.run_id,
                    json_extract(omr.module_result_json, '$.data.age_of_contamination_score') as age_score,
                    json_extract(omr.module_result_json, '$.data.third_party_impact_score') as third_party_score
                FROM orchestration_module_results omr
                WHERE omr.module_name LIKE '%Score Calculation%'
            ) scores ON lr.run_id = scores.run_id
            GROUP BY af.site_id, so.site_name, so.site_address
            ORDER BY latest_feedback DESC
        """)
    
    if feedback_summary.empty:
        st.info("No feedback has been submitted yet.")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Sites with Feedback", len(feedback_summary))
    with col2:
        st.metric("Total Feedback Entries", feedback_summary['feedback_count'].sum())
    with col3:
        avg_age_accuracy = (feedback_summary['age_correct_count'].sum() / feedback_summary['feedback_count'].sum() * 100) if feedback_summary['feedback_count'].sum() > 0 else 0
        st.metric("Age Score Accuracy", f"{avg_age_accuracy:.1f}%")
    with col4:
        avg_tp_accuracy = (feedback_summary['third_party_correct_count'].sum() / feedback_summary['feedback_count'].sum() * 100) if feedback_summary['feedback_count'].sum() > 0 else 0
        st.metric("Third-Party Accuracy", f"{avg_tp_accuracy:.1f}%")
    
    # Export button at the top
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Sites with Feedback")
    with col2:
        if st.button("📥 Export All to CSV", use_container_width=True):
            all_feedback = query_df("""
                SELECT 
                    af.*,
                    so.site_name,
                    so.site_address
                FROM ai_feedback af
                LEFT JOIN site_overview so ON af.site_id = so.site_id
                ORDER BY af.site_id, af.submitted_at DESC
            """)
            
            csv = all_feedback.to_csv(index=False)
            st.download_button(
                label="💾 Download CSV",
                data=csv,
                file_name="ai_feedback_export.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # Check for site_id query parameter to auto-expand
    query_params = st.query_params
    auto_expand_site = query_params.get("site_id", None)
    
    # Create expandable rows for each site with feedback
    base_url = os.environ.get("PROCESS_API_BASE", "http://localhost:5001").rstrip("/")
    
    for idx, row in feedback_summary.iterrows():
        site_id = row['site_id']
        site_name = row['site_name'] or 'No Name'
        
        # Get actual feedback count for this site
        actual_count = query_df("SELECT COUNT(*) as count FROM ai_feedback WHERE site_id = ?", [site_id]).iloc[0]['count']
        
        # Format display values
        age_score = f"{int(row['age_score'])}" if pd.notna(row['age_score']) else "N/A"
        tp_score = f"{int(row['third_party_score'])}" if pd.notna(row['third_party_score']) else "N/A"
        age_feedback = '✅' if row['latest_age_correct'] == 1 else ('❌' if row['latest_age_correct'] == 0 else '—')
        tp_feedback = '✅' if row['latest_third_party_correct'] == 1 else ('❌' if row['latest_third_party_correct'] == 0 else '—')
        
        # Auto-expand if this is the requested site
        should_expand = (str(site_id) == str(auto_expand_site)) if auto_expand_site else False
        
        # Create expander with summary info in the label
        with st.expander(f"**Site {site_id}** - {site_name[:50]}... | Age: {age_score} {age_feedback} | 3rd Party: {tp_score} {tp_feedback} | Feedbacks: {int(actual_count)}", expanded=should_expand):
            # Links to results and site detail pages
            results_url = f"{base_url}/results/{site_id}"
            site_detail_url = f"{URL_PREFIX}/Site_Detail?site_id={site_id}"
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"[🔍 View AI Analysis Results]({results_url})")
            with col2:
                st.markdown(f"[📋 View Site Details]({site_detail_url})")
            
            # Get all feedback for this site
            detailed_feedback = query_df("""
                SELECT 
                    af.*,
                    so.site_name,
                    so.site_address
                FROM ai_feedback af
                LEFT JOIN site_overview so ON af.site_id = so.site_id
                WHERE af.site_id = ?
                ORDER BY af.submitted_at DESC
            """, [site_id])
            
            if not detailed_feedback.empty:
                site_info = detailed_feedback.iloc[0]
                st.write(f"**Site Name:** {site_info['site_name'] or 'Not Available'}")
                st.write(f"**Site Address:** {site_info['site_address'] or 'Not Available'}")
                st.write(f"**Total Feedback Entries:** {len(detailed_feedback)}")
                
                st.divider()
                
                # Display each feedback entry using tabs instead of nested expanders
                if len(detailed_feedback) > 1:
                    tab_labels = [f"Feedback #{i+1}" for i in range(len(detailed_feedback))]
                    tabs = st.tabs(tab_labels)
                    
                    for fb_idx, (feedback, tab) in enumerate(zip(detailed_feedback.itertuples(), tabs)):
                        with tab:
                            st.caption(f"Run ID: {feedback.run_id[:8]}... | Submitted: {feedback.submitted_at}")
                            
                            # Age Score Feedback
                            st.markdown("#### 📅 Age Score Feedback")
                            if pd.notna(feedback.age_correct):
                                if feedback.age_correct:
                                    st.success("✅ Age score was marked as CORRECT")
                                else:
                                    st.error("❌ Age score was marked as INCORRECT")
                            else:
                                st.info("No age score correctness feedback provided")
                            
                            if pd.notna(feedback.age_feedback) and feedback.age_feedback:
                                st.text_area("Detailed Age Feedback", feedback.age_feedback, disabled=True, height=100, key=f"age_{site_id}_{fb_idx}")
                            else:
                                st.caption("No detailed age feedback provided")
                            
                            # Third-Party Feedback
                            st.markdown("#### 🏢 Third-Party Impact Feedback")
                            if pd.notna(feedback.third_party_correct):
                                if feedback.third_party_correct:
                                    st.success("✅ Third-party impact score was marked as CORRECT")
                                else:
                                    st.error("❌ Third-party impact score was marked as INCORRECT")
                            else:
                                st.info("No third-party score correctness feedback provided")
                            
                            if pd.notna(feedback.third_party_feedback) and feedback.third_party_feedback:
                                st.text_area("Detailed Third-Party Feedback", feedback.third_party_feedback, disabled=True, height=100, key=f"tp_{site_id}_{fb_idx}")
                            else:
                                st.caption("No detailed third-party feedback provided")
                            
                            # Document Selection Feedback
                            st.markdown("#### 📄 Document Selection & Priority Feedback")
                            if pd.notna(feedback.document_selection_correct):
                                if feedback.document_selection_correct:
                                    st.success("✅ Document selection and priority order was marked as APPROPRIATE")
                                else:
                                    st.error("❌ Document selection or priority order was marked as NEEDS IMPROVEMENT")
                            else:
                                st.info("No document selection correctness feedback provided")
                            
                            if pd.notna(feedback.document_selection_feedback) and feedback.document_selection_feedback:
                                st.text_area("Detailed Document Selection Feedback", feedback.document_selection_feedback, disabled=True, height=100, key=f"doc_{site_id}_{fb_idx}")
                            else:
                                st.caption("No detailed document selection feedback provided")
                            
                            # Document Details
                            if pd.notna(feedback.selected_documents_shown) and feedback.selected_documents_shown:
                                st.markdown("#### 📋 Documents Shown (Priority Order)")
                                try:
                                    selected_doc_ids = json.loads(feedback.selected_documents_shown)
                                    st.write(f"**Total documents shown:** {len(selected_doc_ids)}")
                                    
                                    # Get document details for these IDs
                                    if selected_doc_ids:
                                        placeholders = ','.join(['?'] * len(selected_doc_ids))
                                        doc_details = query_df(f"""
                                            SELECT 
                                                id,
                                                document_title,
                                                document_type,
                                                document_date,
                                                site_id,
                                                document_url
                                            FROM site_documents
                                            WHERE id IN ({placeholders})
                                        """, selected_doc_ids)
                                        
                                        # Create a map for ordering
                                        doc_map = {str(row['id']): row for _, row in doc_details.iterrows()} if not doc_details.empty else {}
                                        
                                        for i, doc_id in enumerate(selected_doc_ids, 1):
                                            doc_info = doc_map.get(str(doc_id))
                                            if doc_info is not None:
                                                doc_title = doc_info['document_title'] or f"Document {doc_id}"
                                                doc_type = doc_info['document_type'] or ""
                                                doc_date = doc_info['document_date'] or ""
                                                
                                                # Build display name with type and date if available
                                                display_name = doc_title
                                                if doc_type:
                                                    display_name += f" ({doc_type})"
                                                if doc_date:
                                                    display_name += f" - {doc_date}"
                                                
                                                if pd.notna(doc_info['document_url']) and doc_info['document_url']:
                                                    # Create clickable link to WA Ecology site
                                                    st.markdown(f"{i}. [{display_name}]({doc_info['document_url']})")
                                                else:
                                                    st.write(f"{i}. {display_name} (no link available)")
                                            else:
                                                st.write(f"{i}. Document ID: {doc_id} (details not found)")
                                    else:
                                        st.caption("No documents in selection")
                                except Exception as e:
                                    st.write(f"Error loading document list: {str(e)}")
                            else:
                                st.markdown("#### 📋 Documents Shown")
                                st.caption("No document list available for this feedback")
                            
                            # Overall Notes
                            st.markdown("#### 💭 Overall Notes")
                            if pd.notna(feedback.overall_notes) and feedback.overall_notes:
                                st.text_area("Additional Notes", feedback.overall_notes, disabled=True, height=150, key=f"overall_{site_id}_{fb_idx}")
                            else:
                                st.caption("No additional notes provided")
                else:
                    # Single feedback entry - display directly without tabs
                    feedback = detailed_feedback.iloc[0]
                    st.caption(f"Run ID: {feedback['run_id'][:8]}... | Submitted: {feedback['submitted_at']}")
                    
                    # Age Score Feedback
                    st.markdown("#### 📅 Age Score Feedback")
                    if pd.notna(feedback['age_correct']):
                        if feedback['age_correct']:
                            st.success("✅ Age score was marked as CORRECT")
                        else:
                            st.error("❌ Age score was marked as INCORRECT")
                    else:
                        st.info("No age score correctness feedback provided")
                    
                    if pd.notna(feedback['age_feedback']) and feedback['age_feedback']:
                        st.text_area("Detailed Age Feedback", feedback['age_feedback'], disabled=True, height=100, key=f"age_{site_id}_single")
                    else:
                        st.caption("No detailed age feedback provided")
                    
                    # Third-Party Feedback
                    st.markdown("#### 🏢 Third-Party Impact Feedback")
                    if pd.notna(feedback['third_party_correct']):
                        if feedback['third_party_correct']:
                            st.success("✅ Third-party impact score was marked as CORRECT")
                        else:
                            st.error("❌ Third-party impact score was marked as INCORRECT")
                    else:
                        st.info("No third-party score correctness feedback provided")
                    
                    if pd.notna(feedback['third_party_feedback']) and feedback['third_party_feedback']:
                        st.text_area("Detailed Third-Party Feedback", feedback['third_party_feedback'], disabled=True, height=100, key=f"tp_{site_id}_single")
                    else:
                        st.caption("No detailed third-party feedback provided")
                    
                    # Document Selection Feedback
                    st.markdown("#### 📄 Document Selection & Priority Feedback")
                    if pd.notna(feedback['document_selection_correct']):
                        if feedback['document_selection_correct']:
                            st.success("✅ Document selection and priority order was marked as APPROPRIATE")
                        else:
                            st.error("❌ Document selection or priority order was marked as NEEDS IMPROVEMENT")
                    else:
                        st.info("No document selection correctness feedback provided")
                    
                    if pd.notna(feedback['document_selection_feedback']) and feedback['document_selection_feedback']:
                        st.text_area("Detailed Document Selection Feedback", feedback['document_selection_feedback'], disabled=True, height=100, key=f"doc_{site_id}_single")
                    else:
                        st.caption("No detailed document selection feedback provided")
                    
                    # Document Details
                    if pd.notna(feedback['selected_documents_shown']) and feedback['selected_documents_shown']:
                        st.markdown("#### 📋 Documents Shown (Priority Order)")
                        try:
                            selected_doc_ids = json.loads(feedback['selected_documents_shown'])
                            st.write(f"**Total documents shown:** {len(selected_doc_ids)}")
                            
                            # Get document details for these IDs
                            if selected_doc_ids:
                                placeholders = ','.join(['?'] * len(selected_doc_ids))
                                doc_details = query_df(f"""
                                    SELECT 
                                        id,
                                        document_title,
                                        document_type,
                                        document_date,
                                        site_id,
                                        document_url
                                    FROM site_documents
                                    WHERE id IN ({placeholders})
                                """, selected_doc_ids)
                                
                                # Create a map for ordering
                                doc_map = {str(row['id']): row for _, row in doc_details.iterrows()} if not doc_details.empty else {}
                                
                                for i, doc_id in enumerate(selected_doc_ids, 1):
                                    doc_info = doc_map.get(str(doc_id))
                                    if doc_info is not None:
                                        doc_title = doc_info['document_title'] or f"Document {doc_id}"
                                        doc_type = doc_info['document_type'] or ""
                                        doc_date = doc_info['document_date'] or ""
                                        
                                        # Build display name with type and date if available
                                        display_name = doc_title
                                        if doc_type:
                                            display_name += f" ({doc_type})"
                                        if doc_date:
                                            display_name += f" - {doc_date}"
                                        
                                        if pd.notna(doc_info['document_url']) and doc_info['document_url']:
                                            # Create clickable link to WA Ecology site
                                            st.markdown(f"{i}. [{display_name}]({doc_info['document_url']})")
                                        else:
                                            st.write(f"{i}. {display_name} (no link available)")
                                    else:
                                        st.write(f"{i}. Document ID: {doc_id} (details not found)")
                            else:
                                st.caption("No documents in selection")
                        except Exception as e:
                            st.write(f"Error loading document list: {str(e)}")
                    else:
                        st.markdown("#### 📋 Documents Shown")
                        st.caption("No document list available for this feedback")
                    
                    # Overall Notes
                    st.markdown("#### 💭 Overall Notes")
                    if pd.notna(feedback['overall_notes']) and feedback['overall_notes']:
                        st.text_area("Additional Notes", feedback['overall_notes'], disabled=True, height=150, key=f"overall_{site_id}_single")
                    else:
                        st.caption("No additional notes provided")

run()