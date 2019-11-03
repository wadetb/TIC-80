import time
import threading

import http.server
import socketserver

from urllib.parse import urlparse, parse_qs

PORT = 8000

TIC80_SIZE = 1*1024*1024

class TIC:
    def __init__(self):
        self.initplz = True
        self.greeting = 'welcome to collab :)'

        self.data = bytearray(TIC80_SIZE)

        self.condition = threading.Condition()
        self.update_keys = {'data': 0, 'exit': 0}

    def signal_update(self, key):
        with self.condition:
            self.update_keys[key] += 1
            self.condition.notify_all()

    def wait_update(self, keys):
        with self.condition:
            self.condition.wait()
            changed = [k for k, v in self.update_keys.items()
                       if keys.get(k, None) != v]
            keys.update(self.update_keys)
        return changed


tic = TIC()


class CollabHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.end_headers()
            code = 'I' if tic.initplz else '_'
            self.wfile.write(code.encode())
            self.wfile.write(tic.greeting.encode())

        elif self.path == '/watch':
            self.send_response(200)
            self.end_headers()

            keys = {}
            while True:
                changed = tic.wait_update(keys)
                self.wfile.write('\n'.join(changed).encode())

        elif self.path.startswith('/data'):
            query = parse_qs(urlparse(self.path).query)
            offset = int(query['offset'][0])
            size = int(query['size'][0])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(size))
            self.end_headers()

            self.wfile.write(tic.data[offset:offset+size])

        else:
            self.send_response(400)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith('/data'):
            query = parse_qs(urlparse(self.path).query)
            offset = int(query['offset'][0])
            size = int(query['size'][0])

            tic.data[offset:offset+size] = self.rfile.read(size)

            tic.signal_update('data')

            self.send_response(200)
            self.end_headers()

        else:
            self.send_response(400)
            self.end_headers()


class CollabServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass


try:
    server = CollabServer(('localhost', PORT), CollabHandler)
    print('Started http server')
    server.serve_forever()

except KeyboardInterrupt:
    print('Shutting down server')
    server.socket.close()
    tic.signal_update('exit')
