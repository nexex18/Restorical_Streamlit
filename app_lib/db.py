import os
import sqlite3
from typing import Optional, Iterable

import pandas as pd
import streamlit as st


DB_PATH = os.environ.get("ECO_DB_PATH", "/Users/darrensilver/python_projects/Restorical/EndToEndQualificationv3/data/database/ecology_sites.db")


def db_exists(path: Optional[str] = None) -> bool:
    p = path or DB_PATH
    return os.path.exists(p) and os.path.isfile(p)


def _connect(path: Optional[str] = None) -> sqlite3.Connection:
    p = path or DB_PATH
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql: str, params: Optional[Iterable] = None) -> pd.DataFrame:
    """Run a SQL query and return a pandas DataFrame."""
    params = params or []
    with _connect() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df

