"""
db.py

Handles all database interactions, including caching enriched data in a
PostgreSQL database. If a database connection is not configured, it gracefully
falls back to the file-based JSON caching system.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import DictCursor, Json

# --- Database Schema ---
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS company_cache (
    orgnr VARCHAR(20) PRIMARY KEY,
    data JSONB,
    last_updated TIMESTAMP WITH TIME ZONE
);
"""

# --- Database Connection ---
db_conn: Optional[PgConnection] = None


def setup_database(connection_string: Optional[str]):
    """Establishes a connection to the PostgreSQL database."""
    global db_conn
    if not connection_string:
        logging.info(
            "No database connection string. Using file-based cache."
        )
        return

    try:
        db_conn = psycopg2.connect(connection_string)
        with db_conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        db_conn.commit()
        logging.info(
            "Successfully connected to PostgreSQL and ensured cache table exists."
        )
    except OperationalError as e:
        logging.error(
            "Could not connect to PostgreSQL: %s. Falling back to file cache.", e
        )
        db_conn = None


def db_load_from_cache(orgnr: str) -> Optional[Dict[str, Any]]:
    """Loads enriched data from the PostgreSQL cache."""
    if not db_conn:
        return None

    try:
        with db_conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                "SELECT data FROM company_cache WHERE orgnr = %s", (orgnr,)
            )
            result = cursor.fetchone()
            if result:
                logging.debug("DB cache hit for %s.", orgnr)
                # The 'data' column is automatically deserialized from JSONB
                return result['data']
    except psycopg2.Error as e:
        logging.error("Error loading from DB cache for %s: %s", orgnr, e)

    logging.debug("DB cache miss for %s.", orgnr)
    return None


def db_save_to_cache(orgnr: str, data: Dict[str, Any]):
    """Saves enriched data to the PostgreSQL cache."""
    if not db_conn:
        return

    try:
        with db_conn.cursor() as cursor:
            # Use ON CONFLICT to perform an "upsert"
            cursor.execute(
                """
                INSERT INTO company_cache (orgnr, data, last_updated)
                VALUES (%s, %s, %s)
                ON CONFLICT (orgnr) DO UPDATE SET
                    data = EXCLUDED.data,
                    last_updated = EXCLUDED.last_updated;
                """,
                (orgnr, Json(data), datetime.now(timezone.utc))
            )
        db_conn.commit()
        logging.debug("Successfully saved to DB cache for %s.", orgnr)
    except psycopg2.Error as e:
        logging.error("Error saving to DB cache for %s: %s", orgnr, e)
        if db_conn:
            db_conn.rollback()
