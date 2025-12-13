import streamlit as st
from app_lib.db import query_df, db_exists

st.set_page_config(page_title="Sites Explorer", page_icon="🌐", layout="wide")


def load_data(q: str, doc_search: str, has_docs: str, has_contaminants: str, status: str):
    where = []
    params = []
    if q:
        where.append("(COALESCE(site_name,'') LIKE ? OR COALESCE(site_address,'') LIKE ? OR site_id LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like]
    if doc_search:
        where.append("""EXISTS (
            SELECT 1 FROM site_documents sd
            WHERE sd.site_id = site_overview.site_id
            AND LOWER(sd.document_title) LIKE LOWER(?)
        )""")
        params.append(f"%{doc_search}%")
    if has_docs != "Any":
        where.append("has_documents = ?")
        params.append(1 if has_docs == "Yes" else 0)
    if has_contaminants != "Any":
        where.append("has_contaminants = ?")
        params.append(1 if has_contaminants == "Yes" else 0)
    if status != "Any":
        where.append("scrape_status = ?")
        params.append(status)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT site_id, site_name, site_address, total_documents, total_contaminants,
               has_documents, has_contaminants, scrape_status, status_icon
        FROM site_overview
        {where_sql}
        ORDER BY CAST(site_id AS INTEGER)
        LIMIT 3000
    """
    return query_df(sql, params)


def run():
    if not db_exists():
        st.error("Database not found at data/ecology_sites.db")
        st.stop()

    st.title("Sites Explorer 🌐")
    st.caption("Filter, search, and export sites with associated metadata.")

    q = st.text_input("Search (name, address, site_id)", "")
    doc_search = st.text_input("Search By Document Name", "")
    c1, c2, c3 = st.columns(3)
    with c1:
        has_docs = st.selectbox("Has Documents", ["Any", "Yes", "No"], index=0)
    with c2:
        has_contaminants = st.selectbox("Has Contaminants", ["Any", "Yes", "No"], index=0)
    with c3:
        status = st.selectbox("Scrape Status", ["Any", "success", "failed", "pending"])

    df = load_data(q, doc_search, has_docs, has_contaminants, status)
    st.write(f"Results: {len(df):,}")

    st.dataframe(df, use_container_width=True, height=600)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="sites_export.csv",
        mime="text/csv",
    )


run()

