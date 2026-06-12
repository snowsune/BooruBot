from utilities.spoiler import format_link_with_cw, spoiler_tags_for

POST_URL = "https://booru.snowsune.net/posts/42"


class TestSpoilerTagsFor:
    def test_matches_configured_tags(self):
        assert spoiler_tags_for("cute bones humanoid vixi") == ["bones", "humanoid"]

    def test_ignores_unlisted_tags(self):
        assert spoiler_tags_for("cute canine vulpine") == []


class TestFormatLinkWithCw:
    def test_wraps_url_when_tags_match(self):
        assert format_link_with_cw(POST_URL, "bones skull cute") == (
            f"## CW: bones, skull\n|| {POST_URL} ||"
        )

    def test_returns_plain_url_when_no_match(self):
        assert format_link_with_cw(POST_URL, "cute canine") == POST_URL
