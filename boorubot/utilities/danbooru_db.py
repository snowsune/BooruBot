import os

FAVORITE_NOTIFY_CHANNEL = "favorite_added"

RATING_NAMES = {
    "g": "general",
    "s": "sensitive",
    "q": "questionable",
    "e": "explicit",
}


def post_matches_filter(tag_string, rating, filter_query):
    """Match a post against my filter checker"""
    tags = set(tag_string.split())
    rating_name = RATING_NAMES.get(rating, rating)

    for token in filter_query.split():
        if token.startswith("-rating:"):
            if rating_name == token[8:]:
                return False
        elif token.startswith("rating:"):
            if rating_name != token[7:]:
                return False
        elif token.startswith("-"):
            if token[1:] in tags:
                return False
        elif token not in tags:
            return False

    return True


def _connect_kwargs():
    return {
        "dbname": os.getenv("DANBOORU_DB_NAME", "danbooru"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASS"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
    }


def connect():
    import psycopg

    return psycopg.connect(**_connect_kwargs())


async def connect_async():
    import psycopg

    return await psycopg.AsyncConnection.connect(autocommit=True, **_connect_kwargs())


async def fetch_fav_context(user_id, post_id):
    async with await connect_async() as conn:
        cur = await conn.execute(
            """
            SELECT u.name, p.tag_string, p.rating
            FROM users u
            JOIN posts p ON p.id = %s
            WHERE u.id = %s
            """,
            (post_id, user_id),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return row[0], row[1], row[2]
