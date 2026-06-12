#!/usr/bin/env python3
"""Check that notify is on for the things we care about"""

from utilities.danbooru_db import connect

EXPECTED_TRIGGER = "favorites_notify_trg"


def main():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT tgname, pg_get_triggerdef(t.oid)
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = 'favorites' AND NOT t.tgisinternal
            """
        ).fetchall()

    if not rows:
        print("FAIL: no triggers on public.favorites")
        return 1

    for name, definition in rows:
        print(f"{name}: {definition}")

    names = [name for name, _ in rows]
    if EXPECTED_TRIGGER not in names:
        print(f"FAIL: expected trigger {EXPECTED_TRIGGER!r} not found")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
