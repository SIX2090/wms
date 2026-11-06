"""Read the actual material markup and its extracted executable page asset."""
from pathlib import Path


def material_page_source():
    root = Path(__file__).resolve().parents[1]
    html = (root / 'app/templates/material.html').read_text(encoding='utf-8')
    script = (root / 'app/static/js/pages/material-list.js').read_text(encoding='utf-8')
    # Keep existing HTML/function extractors exercising the shipped code.
    return html + '\n<script>\n' + script + '\n</script>'
