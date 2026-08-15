"""Unit tests for styles.icon_colors — theme color mapping."""

import pytest

from styles.icon_colors import get_icon_color, DARK, LIGHT, DEFAULT_DARK, DEFAULT_LIGHT


class TestGetIconColor:
    def test_dark_theme_known_icon(self):
        color = get_icon_color("save.svg", dark=True)
        assert color == "#4fc080"

    def test_light_theme_known_icon(self):
        color = get_icon_color("save.svg", dark=False)
        assert color == "#1a7a40"

    def test_unknown_icon_returns_default_dark(self):
        color = get_icon_color("nonexistent.svg", dark=True)
        assert color == DEFAULT_DARK

    def test_unknown_icon_returns_default_light(self):
        color = get_icon_color("nonexistent.svg", dark=False)
        assert color == DEFAULT_LIGHT

    def test_all_dark_icons_have_light_counterpart(self):
        for svg_file in DARK:
            assert svg_file in LIGHT, f"{svg_file} missing from LIGHT dict"

    def test_all_light_icons_have_dark_counterpart(self):
        for svg_file in LIGHT:
            assert svg_file in DARK, f"{svg_file} missing from DARK dict"
