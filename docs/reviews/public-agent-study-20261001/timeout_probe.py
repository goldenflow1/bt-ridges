import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, '/root/bittensor/ridges/src')
from quarry.llm import urllib_transport

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header('Content-Length', '20')
        self.end_headers()
        for _ in range(20):
            self.wfile.write(b' ')
            self.wfile.flush()
            time.sleep(0.03)
    def log_message(self, *_):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
started = time.monotonic()
try:
    status, body = urllib_transport(f'http://127.0.0.1:{server.server_port}', b'{}', {}, 0.1)
    elapsed = time.monotonic() - started
    result = {'test':'local HTTP server sends 20 bytes at 30 ms intervals',
              'requested_timeout_sec':0.1, 'elapsed_sec':round(elapsed,3),
              'status':status, 'received_bytes':len(body),
              'exceeded_requested_timeout':elapsed > 0.3,
              'interpretation':'Socket timeout does not bound total response duration. This reproduces a local transport deadline gap, not the production screening failure.'}
    print(json.dumps(result,indent=2))
    open('/tmp/quarry-timeout-probe.json','w').write(json.dumps(result,indent=2)+'\n')
finally:
    server.shutdown()
    server.server_close()
