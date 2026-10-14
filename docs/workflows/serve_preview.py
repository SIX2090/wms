"""Read-only local atlas preview. Does not expose the WMS application directory."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

DOCS = Path(__file__).resolve().parent
PDF = DOCS.parents[1] / 'output/pdf/wms_flow_atlas_20261014.pdf'


class AtlasHandler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(DOCS),**kwargs)

    def do_GET(self):
        route=unquote(urlsplit(self.path).path)
        if route=='/output/pdf/wms_flow_atlas_20261014.pdf':
            data=PDF.read_bytes()
            self.send_response(200);self.send_header('Content-Type','application/pdf')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            return
        relative=route.lstrip('/') or 'index.html'
        target=(DOCS/relative).resolve()
        if not target.is_relative_to(DOCS) or target.suffix not in {'.html','.svg','.json','.md'} or not target.is_file():
            self.send_error(404);return
        super().do_GET()

    def do_HEAD(self):
        self.send_response(405);self.end_headers()

    def do_POST(self):
        self.send_response(405);self.end_headers()


if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',18082),AtlasHandler).serve_forever()
