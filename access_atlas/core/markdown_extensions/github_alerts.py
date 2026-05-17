from __future__ import annotations

import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

ALERT_MARKER_RE = re.compile(r"^>\s*\[!(?P<type>[A-Za-z]+)]\s*$")
BLOCKQUOTE_RE = re.compile(r"^>\s?(?P<content>.*)$")

ALERT_TYPES = {
    "NOTE": "note",
    "TIP": "tip",
    "IMPORTANT": "info",
    "WARNING": "warning",
    "CAUTION": "danger",
}


class GitHubAlertPreprocessor(Preprocessor):
    """Convert GitHub blockquote alerts into Python Markdown admonitions."""

    def run(self, lines: list[str]) -> list[str]:
        converted: list[str] = []
        index = 0
        while index < len(lines):
            marker = ALERT_MARKER_RE.match(lines[index])
            if not marker:
                converted.append(lines[index])
                index += 1
                continue

            alert_type = marker.group("type").upper()
            admonition_type = ALERT_TYPES.get(alert_type)
            if admonition_type is None:
                converted.append(lines[index])
                index += 1
                continue

            index += 1
            body: list[str] = []
            while index < len(lines):
                body_match = BLOCKQUOTE_RE.match(lines[index])
                if body_match is None:
                    break
                body.append(body_match.group("content"))
                index += 1

            converted.append(f'!!! {admonition_type} "{alert_type}"')
            converted.extend(_indent_alert_body(body))
            continue

        return converted


def _indent_alert_body(lines: list[str]) -> list[str]:
    body = lines or [""]
    return [f"    {line}" if line else "" for line in body]


class GitHubAlertsExtension(Extension):
    """Register support for GitHub-flavored Markdown alert blockquotes."""

    def extendMarkdown(self, md):
        md.preprocessors.register(
            GitHubAlertPreprocessor(md),
            "github_alerts",
            28,
        )


def makeExtension(**kwargs):
    return GitHubAlertsExtension(**kwargs)
