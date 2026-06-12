#!/usr/bin/env python3
"""Listen for favorite_added NOTIFY events from the booru DB."""

import json

from utilities.danbooru_db import FAVORITE_NOTIFY_CHANNEL, connect


def main():
    with connect() as conn:
        conn.autocommit = True
        conn.execute(f"LISTEN {FAVORITE_NOTIFY_CHANNEL}")
        print(f"Listening on {FAVORITE_NOTIFY_CHANNEL} (Ctrl+C to stop)...")

        for notify in conn.notifies():
            print(json.loads(notify.payload))


if __name__ == "__main__":
    main()
