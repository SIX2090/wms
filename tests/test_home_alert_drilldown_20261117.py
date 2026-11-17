"""Both home alert links must use the same warehouse scope as their count."""
from pathlib import Path
import re
from urllib.parse import urlencode
from jinja2 import Environment


def test_home_alert_drilldown_preserves_warehouse():
    source = (Path(__file__).resolve().parents[1] / 'app/templates/index.html').read_text(encoding='utf-8')
    links = [href for href in re.findall(r'href="([^"]+)"', source)
             if 'stock_filter=low' in href or "url_for('alert_list'" in href]
    assert len(links) == 2
    for warehouse_id in (0, 1, 2):
        env = Environment(autoescape=True)
        for href in links:
            rendered = env.from_string(href).render(
                alert_warehouse_id=warehouse_id,
                url_for=lambda endpoint, **values: '/alert?' + urlencode(values))
            assert rendered == '/alert?warehouse_id=' + str(warehouse_id)
