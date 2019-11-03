import struct
import time
import threading

import http.server
import socketserver

from urllib.parse import urlparse, parse_qs


PORT = 8000
PROTOCOL_VERSION = 1
TIC80_SIZE = 1*1024*1024


class TIC:
    def __init__(self):
        self.init_needed = True
        self.greeting = 'welcome to collab :)'

        self.mem = bytearray(TIC80_SIZE)

        self.condition = threading.Condition()
        self.watchers = {}

    def signal_update(self, offset, size):
        with self.condition:
            for k in self.watchers.keys():
                self.watchers[k].append((offset, size))
            self.condition.notify_all()

    def watch(self, client_key):
        pending_updates = []
        self.watchers[client_key] = pending_updates
        while True:
            with self.condition:
                self.condition.wait()
                while len(pending_updates):
                    yield pending_updates.pop()


tic = TIC()


class CollabHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            content = struct.pack('<bb', PROTOCOL_VERSION, tic.init_needed) + tic.greeting.encode()

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(content)))
            self.end_headers()

            self.wfile.write(content)

            tic.init_needed = False
            
        elif self.path == '/watch':
            self.send_response(200)
            self.end_headers()

            for offset, size in tic.watch(self.client_address):
                if offset is None:
                    break
                self.wfile.write(struct.pack('<ii', offset, size))
                self.wfile.write(tic.mem[offset:offset+size])

        elif self.path.startswith('/data'):
            query = parse_qs(urlparse(self.path).query)
            offset = int(query['offset'][0])
            size = int(query['size'][0])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(size))
            self.end_headers()

            self.wfile.write(tic.mem[offset:offset+size])

        else:
            self.send_response(400)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith('/data'):
            query = parse_qs(urlparse(self.path).query)
            offset = int(query['offset'][0])
            size = int(query['size'][0])

            tic.mem[offset:offset+size] = self.rfile.read(size)
            tic.signal_update(offset, size)

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
    tic.signal_update(None, None)
