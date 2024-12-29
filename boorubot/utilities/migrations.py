import psycopg
import logging
import os
from datetime import datetime

from .database import getCur

"""
We could use a library but we can also manually track/handle basic migrations here,
no reason we couldn't migrate (lol) in the future
"""


# For the first boot
def init_migration_log():
    cur, conn = getCur()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS migration_log (
            id SERIAL PRIMARY KEY,
            migration_name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    conn.commit()
    cur.close()
    conn.close()


# Applies a migration
def apply_migration(migration_name, migration_func):
    cur, conn = getCur()

    # Check if the migration has already been applied
    cur.execute(
        """
        SELECT 1 FROM migration_log WHERE migration_name = %s;
    """,
        (migration_name,),
    )

    if cur.fetchone():
        logging.info(f"Migration {migration_name} already applied.")
    else:
        # Run the migration function
        logging.info(f"Applying migration {migration_name}...")
        migration_func(cur)

        # Log the migration as applied
        cur.execute(
            """
            INSERT INTO migration_log (migration_name) VALUES (%s);
        """,
            (migration_name,),
        )
        conn.commit()

    cur.close()
    conn.close()


def create_key_value_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS key_value_store (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """
    )


def init_migrations():
    init_migration_log()

    # Apply migrations
    apply_migration("create_key_value_table", create_key_value_table)
