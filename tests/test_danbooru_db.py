from utilities.danbooru_db import post_matches_filter


class TestPostMatchesFilter:
    def test_sfw_channel(self):
        tags = "cute canine rating:g"
        assert post_matches_filter(tags, "g", "rating:general -vore -gore") is True
        assert post_matches_filter("vore cute", "g", "rating:general -vore -gore") is False
        assert post_matches_filter("cute", "e", "rating:general -vore -gore") is False

    def test_main_channel_excludes_general(self):
        tags = "cute canine"
        assert post_matches_filter(tags, "e", "-vore -rating:general") is True
        assert post_matches_filter(tags, "g", "-vore -rating:general") is False

    def test_vore_channel(self):
        tags = "cute vore"
        assert post_matches_filter(tags, "g", "vore -gore") is True
        assert post_matches_filter("cute", "g", "vore -gore") is False
