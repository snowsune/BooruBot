import os

SPOILER_TAGS = {
    t.strip().lower()
    for t in os.getenv(
        "SPOILER_TAGS",
        "gore bestiality noncon bones humanoid skull human disposal death fatal",
    ).split()
    if t.strip()
}


def spoiler_tags_for(tag_string):
    tags = {t.lower() for t in tag_string.split()}
    return sorted(tag for tag in tags if tag in SPOILER_TAGS)


def format_link_with_cw(post_url, tag_string):
    hit = spoiler_tags_for(tag_string)
    if hit:
        return f"## CW: {', '.join(hit)}\n|| {post_url} ||"
    return post_url
