from __future__ import annotations

import json
import re


def parse_json_script(content: str, script_id: str):
    match = re.search(
        rf'<script id="{script_id}" type="application/json">(.*?)</script>',
        content,
        re.DOTALL,
    )
    assert match is not None, f"Missing json_script payload: {script_id}"
    return json.loads(match.group(1))
