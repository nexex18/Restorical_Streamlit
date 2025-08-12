import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Documents", page_icon="📄", layout="wide")


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Documents 📄")
    st.caption("Explore documents by category, date, and status.")

    cats = query_df("SELECT DISTINCT COALESCE(document_category,'Uncategorized') AS c FROM site_documents ORDER BY c")
    statuses = query_df("SELECT DISTINCT COALESCE(download_status,'unknown') AS s FROM site_documents ORDER BY s")

    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        category = st.multiselect("Category", cats["c"].tolist(), [])
    with c2:
        status = st.multiselect("Download Status", statuses["s"].tolist(), [])
    with c3:
        year = st.text_input("Year Contains (e.g. 2018)", "")

    where, params = [], []
    if category:
        where.append("COALESCE(document_category,'Uncategorized') IN (%s)" % (",".join(["?"]*len(category))))
        params += category
    if status:
        where.append("COALESCE(download_status,'unknown') IN (%s)" % (",".join(["?"]*len(status))))
        params += status
    if year:
        where.append("COALESCE(document_date,'') LIKE ?")
        params.append(f"%{year}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT id, site_id, document_category, document_title, document_date, document_type,
               document_url, download_status, flagged_for_analysis, file_extension, file_size_bytes
        FROM site_documents
        {where_sql}
        ORDER BY id DESC
        LIMIT 5000
    """
    df = query_df(sql, params)

    st.write(f"Results: {len(df):,}")
    st.dataframe(df, use_container_width=True, height=600)
    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="documents_export.csv",
        mime="text/csv",
    )


run()

