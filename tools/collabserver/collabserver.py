#!/usr/bin/python3
#
# MIT License
#
# Copyright (c) 2019 Wade Brainerd - wadetb@gmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import pathlib
import re
import struct
import time
import threading

import http.server
import socketserver

from urllib.parse import urlparse, parse_qs

PORT = 8000
PROTOCOL_VERSION = 1

TIC80_SIZE = 1 * 1024 * 1024

DATA_PATH = 'data'
DATA_EXT = '.tic_collab'


class TIC:
    def __init__(self, name):
        self.path = (pathlib.Path(DATA_PATH) / name).with_suffix(DATA_EXT)
        
        if not self.path.exists():
            with self.path.open('wb') as file:
                file.write(b'\0' * TIC80_SIZE)
            self.init_needed = True
        else:
            self.init_needed = False

        self.file = self.path.open('r+b', buffering=0)

        self.condition = threading.Condition()
        self.watchers = {}

    def read_mem(self, offset, size):
        self.file.seek(offset)
        return self.file.read(size)

    def write_mem(self, offset, data):
        self.file.seek(offset)
        self.file.write(data)

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


class CollabRequestHandler(http.server.BaseHTTPRequestHandler):
    def lookup_tic(self, path):
        name = path.replace('/', '').lower()

        if re.match(r'[^a-z_-]', name):
            raise ValueError

        if not name in self.server.tics:
            self.server.tics[name] = TIC(name)

        return self.server.tics[name]

    def send_response_with_content(self, content):
        self.send_response(200)
        self.send_header('Content-Length', '{}'.format(len(content)))
        self.end_headers()

        self.wfile.write(content)

    def do_request(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)

        try:
            tic = self.lookup_tic(url.path)

            if self.command == 'GET':
                if not len(query):
                    header = struct.pack('<bb', PROTOCOL_VERSION,
                                         tic.init_needed)
                    greeting = self.server.greeting.encode()
                    self.send_response_with_content(header + greeting)
                    tic.init_needed = False

                elif 'watch' in query:
                    self.send_response(200)
                    self.end_headers()

                    for offset, size in tic.watch(self.client_address):
                        if offset is None:
                            break
                        self.wfile.write(struct.pack('<ii', offset, size))

                elif 'offset' in query:
                    offset = int(query['offset'][0])
                    size = int(query['size'][0])

                    self.send_response_with_content(tic.read_mem(offset, size))

            elif self.command == 'PUT':
                offset = int(query['offset'][0])
                size = int(query['size'][0])

                tic.write_mem(offset, self.rfile.read(size))
                tic.signal_update(offset, size)

                self.send_response(200)
                self.end_headers()

        except ValueError:
            self.send_error(400)
        except BrokenPipeError:
            pass
        except OSError:
            self.send_error(500)

    def do_GET(self):
        self.do_request()

    def do_PUT(self):
        self.do_request()


class CollabServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    def __init__(self, addr):
        super().__init__(addr, CollabRequestHandler)
        self.greeting = 'welcome to collab :)'
        
        self.tics = {}

        self.data_path = pathlib.Path(DATA_PATH)
        self.data_path.mkdir(exist_ok=True)

    def shutdown(self):
        self.socket.close()
        for tic in self.tics.values():
            tic.signal_update(None, None)


try:
    server = CollabServer(('localhost', PORT))
    print('Started http server')
    server.serve_forever()

except KeyboardInterrupt:
    print('Shutting down server')
    server.shutdown()
