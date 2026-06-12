import os
import logging
import psycopg


def getCur():
    conn = psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )
    cur = conn.cursor()
    return cur, conn


def store_key(key, value):
    cur, conn = getCur()

    # if in debug mode, prepend debug_ to key
    if os.getenv("DEBUG", "False").lower() in ("true", "1", "yes"):
        key = f"debug_{key}"

    cur.execute(
        """
    INSERT INTO key_value_store (key, value)
    VALUES (%s, %s)
    ON CONFLICT (key) 
    DO UPDATE SET value = EXCLUDED.value
    """,
        (key, value),
    )
    conn.commit()
    cur.close()
    conn.close()


def retrieve_key(key, default=None):
    cur, conn = getCur()

    # if in debug mode, prepend debug_ to key
    if os.getenv("DEBUG", "False").lower() in ("true", "1", "yes"):
        key = f"debug_{key}"

    cur.execute(
        """
    SELECT value FROM key_value_store WHERE key = %s
    """,
        (key,),
    )
    result = cur.fetchone()
    cur.close()
    conn.close()

    # If key empty/missing
    if not result:
        if default is not None:
            store_key(key, default)
            logging.warning(f"Inserting default {default} into key {key}")
        return default

    # otherwise return key
    return result[0]
