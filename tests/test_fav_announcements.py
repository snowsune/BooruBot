from utilities.fav_announcements import (
    format_fav_announcement,
    format_fav_message,
    merge_fav_announcement,
    parse_fav_message,
)

POST_URL = "https://booru.snowsune.net/posts/21944"
SPOILER_LINK = f"## CW: bones, skull\n|| {POST_URL} ||"


class TestParseFavMessage:
    def test_single_user(self):
        content = f"**Vixi** added a new favorite!\n{POST_URL}"
        assert parse_fav_message(content) == (21944, ["Vixi"], POST_URL)

    def test_two_users(self):
        content = f"**Vixi** and **Tirga** added a new favorite!\n{POST_URL}"
        assert parse_fav_message(content) == (21944, ["Vixi", "Tirga"], POST_URL)

    def test_three_users(self):
        content = f"**Vixi**, **Tirga**, and **Randal** added a new favorite!\n{POST_URL}"
        assert parse_fav_message(content) == (21944, ["Vixi", "Tirga", "Randal"], POST_URL)

    def test_spoiler_link(self):
        content = f"**Vixi** added a new favorite!\n{SPOILER_LINK}"
        assert parse_fav_message(content) == (21944, ["Vixi"], SPOILER_LINK)

    def test_rejects_unrelated_message(self):
        assert parse_fav_message("hello world") is None


class TestFormatFavMessage:
    def test_single_user(self):
        assert (
            format_fav_message(["Vixi"], POST_URL)
            == f"**Vixi** added a new favorite!\n{POST_URL}"
        )

    def test_two_users(self):
        assert (
            format_fav_message(["Vixi", "Tirga"], POST_URL)
            == f"**Vixi** and **Tirga** added a new favorite!\n{POST_URL}"
        )

    def test_three_users(self):
        assert (
            format_fav_message(["Vixi", "Tirga", "Randal"], POST_URL)
            == f"**Vixi**, **Tirga**, and **Randal** added a new favorite!\n{POST_URL}"
        )


class TestFormatFavAnnouncement:
    def test_adds_cw_for_spoiler_tags(self):
        content = format_fav_announcement(
            ["Vixi"],
            POST_URL,
            "cute canine bones skull vulpine",
        )
        assert content == f"**Vixi** added a new favorite!\n{SPOILER_LINK}"

    def test_plain_link_without_spoiler_tags(self):
        content = format_fav_announcement(
            ["Vixi"],
            POST_URL,
            "cute canine vulpine",
        )
        assert content == f"**Vixi** added a new favorite!\n{POST_URL}"


class TestMergeFavAnnouncement:
    def test_adds_new_username(self):
        parsed = (21944, ["Vixi"], POST_URL)
        merged = merge_fav_announcement(parsed, "Tirga")
        assert merged == format_fav_message(["Vixi", "Tirga"], POST_URL)

    def test_preserves_spoiler_link_section(self):
        parsed = (21944, ["Vixi"], SPOILER_LINK)
        merged = merge_fav_announcement(parsed, "Tirga")
        assert merged == format_fav_message(["Vixi", "Tirga"], SPOILER_LINK)

    def test_skips_duplicate_username(self):
        parsed = (21944, ["Vixi", "Tirga"], POST_URL)
        assert merge_fav_announcement(parsed, "Tirga") is None
