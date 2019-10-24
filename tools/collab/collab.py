import time
import threading

import http.server
import socketserver

from urllib.parse import urlparse, parse_qs

PORT = 8000

TIC80_WIDTH = 240
TIC80_HEIGHT = 136

TOOLBAR_SIZE = 7

BITS_IN_BYTE = 8

TIC_PALETTE_BPP = 4
TIC_PALETTE_SIZE = (1 << TIC_PALETTE_BPP)
TIC_PALETTE_CHANNELS = 3

TIC_BANK_SPRITES = (1 << BITS_IN_BYTE)
TIC_SPRITE_BANKS = 2
TIC_SPRITES = (TIC_BANK_SPRITES * TIC_SPRITE_BANKS)
TIC_SPRITESIZE = 8
TIC_SPRITESHEET_COLS = 16
TIC_SPRITESHEET_SIZE = (TIC_SPRITESHEET_COLS * TIC_SPRITESIZE)

TIC_FLAGS = (TIC_BANK_SPRITES * TIC_SPRITE_BANKS)

TIC_MAP_ROWS = TIC_SPRITESIZE
TIC_MAP_COLS = TIC_SPRITESIZE
TIC_MAP_SCREEN_WIDTH = TIC80_WIDTH // TIC_SPRITESIZE
TIC_MAP_SCREEN_HEIGHT = TIC80_HEIGHT // TIC_SPRITESIZE
TIC_MAP_WIDTH = TIC_MAP_SCREEN_WIDTH * TIC_MAP_ROWS
TIC_MAP_HEIGHT = TIC_MAP_SCREEN_HEIGHT * TIC_MAP_COLS

class TIC:
    def __init__(self):
        self.greeting = 'welcome to collab :)'

        self.tiles = [bytearray(b'\0' * (TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE)) 
                      for _ in range(TIC_BANK_SPRITES * TIC_SPRITE_BANKS)]
        self.flags = bytearray(b'\0' * TIC_FLAGS)
        self.palette = bytearray(b'\0' * TIC_PALETTE_SIZE * TIC_PALETTE_CHANNELS)

        self.map = bytearray(b'\0' * TIC_MAP_WIDTH * TIC_MAP_HEIGHT)

        self.condition = threading.Condition()
        self.update_keys = {'sprite': 0, 'flags': 0, 'palette': 0, 'map': 0}

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
            self.wfile.write(tic.greeting.encode())

        elif self.path == '/watch':
            self.send_response(200)
            self.end_headers()

            keys = {}
            while True:
                changed = tic.wait_update(keys)
                self.wfile.write('\n'.join(changed).encode())

        elif self.path.startswith('/sprite/all'):
            buffer = bytearray()
            for index in range(TIC_SPRITES):
                buffer.extend(tic.tiles[index])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/sprite/single'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])
            size = int(query['size'][0])

            size_in_tiles = size // TIC_SPRITESIZE
            buffer = bytearray()
            for y in range(size_in_tiles):
                for x in range(size_in_tiles):
                    buffer.extend(tic.tiles[index + y * TIC_SPRITESHEET_COLS + x])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/flags/all'):
            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(TIC_FLAGS))
            self.end_headers()

            self.wfile.write(tic.flags)

        elif self.path.startswith('/flags/single'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])
            size = int(query['size'][0])

            size_in_tiles = size // TIC_SPRITESIZE
            buffer = bytearray()
            for y in range(size_in_tiles):
                for x in range(size_in_tiles):
                    buffer.append(tic.flags[index + y * TIC_SPRITESHEET_COLS + x])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/palette'):
            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(TIC_PALETTE_SIZE * TIC_PALETTE_CHANNELS))
            self.end_headers()

            self.wfile.write(tic.palette)

        elif self.path.startswith('/map/all'):
            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(TIC_MAP_WIDTH * TIC_MAP_HEIGHT))
            self.end_headers()

            self.wfile.write(tic.map)

        else:
            self.send_response(400)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith('/sprite/all'):
            for index in range(TIC_SPRITES):
                tile = self.rfile.read(TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE)
                tic.tiles[index] = tile

            tic.signal_update('sprite')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/sprite/single'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])
            size = int(query['size'][0])

            size_in_tiles = size // TIC_SPRITESIZE
            for y in range(size_in_tiles):
                for x in range(size_in_tiles):
                    tile = self.rfile.read(TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE)
                    tic.tiles[index + y * TIC_SPRITESHEET_COLS + x] = tile

            tic.signal_update('sprite')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/flags/all'):
            tic.flags = bytearray(self.rfile.read(TIC_FLAGS))

            tic.signal_update('flags')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/flags/single'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])
            size = int(query['size'][0])

            size_in_tiles = size // TIC_SPRITESIZE
            for y in range(size_in_tiles):
                for x in range(size_in_tiles):
                    flag = self.rfile.read(1)[0]
                    tic.flags[index + y * TIC_SPRITESHEET_COLS + x] = flag

            tic.signal_update('flags')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/palette'):
            tic.palette = bytearray(self.rfile.read(TIC_PALETTE_SIZE * TIC_PALETTE_CHANNELS))

            tic.signal_update('palette')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/map/all'):
            tic.map = bytearray(self.rfile.read(TIC_MAP_WIDTH * TIC_MAP_HEIGHT))

            tic.signal_update('map')

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
