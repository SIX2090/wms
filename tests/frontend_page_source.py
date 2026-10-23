"""Read a template and the actual local scripts referenced by its script tags."""
import re
from pathlib import Path


def page_source(path):
    path = Path(path)
    return page_html_source(path.read_text(encoding="utf-8"))


def page_html_source(source):
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    def load(match):
        tag = match.group(0)
        filename = re.search(r"filename\s*=\s*['\"]([^'\"]+\.js)['\"]", tag)
        if not filename:
            filename = re.search(r"/static/(js/pages/(?:opening-stock|print-template-editor)\.js)", tag)
        if not filename or not filename.group(1).startswith("js/pages/"):
            return tag
        target = (static / filename.group(1)).resolve()
        assert target.is_relative_to(static.resolve()), target
        return tag + "\n" + target.read_text(encoding="utf-8")
    return re.sub(r"<script\b[^>]*\bsrc=[^>]*>\s*</script>", load, source)


def page_style_source(path):
    """Keep style behavior assertions bound to the sheets the template loads."""
    source = Path(path).read_text(encoding="utf-8")
    static = (Path(__file__).resolve().parents[1] / "app/static").resolve()

    def load(match):
        tag = match.group(0)
        filename = re.search(r"filename\s*=\s*['\"](css/[^'\"]+\.css)['\"]", tag)
        if not filename:
            return tag
        target = (static / filename.group(1)).resolve()
        assert target.is_relative_to(static), target
        return tag + "\n" + target.read_text(encoding="utf-8")

    return re.sub(r"<link\b[^>]*>", load, source)
