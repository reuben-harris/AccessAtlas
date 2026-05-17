import markdown


def render_markdown(value: str) -> str:
    return markdown.markdown(
        value,
        extensions=[
            "admonition",
            "access_atlas.core.markdown_extensions.github_alerts",
        ],
    )


def test_github_alerts_render_as_admonitions():
    html = render_markdown("> [!WARNING]\n> Keep synced site fields read-only.")

    assert 'class="admonition warning"' in html
    assert "WARNING" in html
    assert "Keep synced site fields read-only." in html


def test_github_alerts_map_caution_to_danger_admonitions():
    html = render_markdown("> [!CAUTION]\n> Confirm destructive workflow changes.")

    assert 'class="admonition danger"' in html
    assert "CAUTION" in html
