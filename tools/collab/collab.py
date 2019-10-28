import time
import threading

import http.server
import socketserver

from urllib.parse import urlparse, parse_qs

PORT = 8000

BITS_IN_BYTE = 8

TIC80_WIDTH = 240
TIC80_HEIGHT = 136

TOOLBAR_SIZE = 7

TIC_PALETTE_BPP = 4
TIC_PALETTE_SIZE = 1 << TIC_PALETTE_BPP
TIC_PALETTE_CHANNELS = 3

TIC_BANK_SPRITES = 1 << BITS_IN_BYTE
TIC_SPRITE_BANKS = 2
TIC_SPRITES = TIC_BANK_SPRITES * TIC_SPRITE_BANKS
TIC_SPRITESIZE = 8
TIC_SPRITESHEET_COLS = 16
TIC_SPRITESHEET_SIZE = TIC_SPRITESHEET_COLS * TIC_SPRITESIZE

TIC_FLAGS = TIC_BANK_SPRITES * TIC_SPRITE_BANKS

TIC_MAP_ROWS = TIC_SPRITESIZE
TIC_MAP_COLS = TIC_SPRITESIZE
TIC_MAP_SCREEN_WIDTH = TIC80_WIDTH // TIC_SPRITESIZE
TIC_MAP_SCREEN_HEIGHT = TIC80_HEIGHT // TIC_SPRITESIZE
TIC_MAP_WIDTH = TIC_MAP_SCREEN_WIDTH * TIC_MAP_ROWS
TIC_MAP_HEIGHT = TIC_MAP_SCREEN_HEIGHT * TIC_MAP_COLS

SFX_COUNT_BITS = 6
SFX_COUNT = (1 << SFX_COUNT_BITS)

SFX_TICKS = 30
SAMPLE_SIZE = SFX_TICKS * 2 + 2 + 4 # 30*2:data, 2:misc, 4:loops

ENVELOPES_COUNT = 16
ENVELOPE_VALUES = 32
ENVELOPE_VALUE_BITS = 4
ENVELOPE_SIZE = ENVELOPE_VALUES * ENVELOPE_VALUE_BITS // BITS_IN_BYTE

TIC_SOUND_CHANNELS = 4

MUSIC_PATTERNS = 60
MUSIC_PATTERN_ROWS = 64
TIC_PATTERN_SIZE = MUSIC_PATTERN_ROWS * 3

MUSIC_TRACKS_BITS = 3
MUSIC_TRACKS = 1 << MUSIC_TRACKS_BITS
MUSIC_FRAMES = 16
TRACK_PATTERN_BITS = 6
TRACK_PATTERNS_SIZE = TRACK_PATTERN_BITS * TIC_SOUND_CHANNELS // BITS_IN_BYTE
TIC_TRACK_SIZE = MUSIC_FRAMES * TRACK_PATTERNS_SIZE + 3

TIC_CODE_SIZE = 64 * 1024


class TIC:
    def __init__(self):
        self.initplz = True
        self.greeting = 'welcome to collab :)'

        self.tiles = [bytearray(b'\0' * (TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE)) 
                      for _ in range(TIC_BANK_SPRITES * TIC_SPRITE_BANKS)]
        self.flags = bytearray(b'\0' * TIC_FLAGS)
        self.palette = bytearray(b'\0' * TIC_PALETTE_SIZE * TIC_PALETTE_CHANNELS)

        self.map = bytearray(b'\0' * TIC_MAP_WIDTH * TIC_MAP_HEIGHT)

        self.samples = [bytearray(b'\0' * SAMPLE_SIZE) for _ in range(SFX_COUNT)]
        self.envelopes = [bytearray(b'\0' * ENVELOPE_SIZE) for _ in range(ENVELOPES_COUNT)]

        self.patterns = [bytearray(b'\0' * TIC_PATTERN_SIZE) for _ in range(MUSIC_PATTERNS)]
        self.tracks = [bytearray(b'\0' * TIC_TRACK_SIZE) for _ in range(MUSIC_TRACKS)]

        self.code = bytearray(b'\0' * TIC_CODE_SIZE)

        self.condition = threading.Condition()
        self.update_keys = {'sprite': 0, 'flags': 0, 'palette': 0, 'map': 0, 'sfx': 0, 'music': 0, 'code': 0, 'exit': 0}

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
            self.wfile.write(code)
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

        elif self.path.startswith('/map/selection'):
            query = parse_qs(urlparse(self.path).query)
            sel_x = int(query['x'][0])
            sel_y = int(query['y'][0])
            sel_w = int(query['w'][0])
            sel_h = int(query['h'][0])

            buffer = bytearray()
            for y in range(sel_y, sel_y+sel_h):
                for x in range(sel_x, sel_x+sel_w):
                    buffer.append(tic.map[y * TIC_MAP_WIDTH + x])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/sample/all'):
            buffer = bytearray()
            for sample in tic.samples:
                buffer.extend(sample)

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/sample/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(SAMPLE_SIZE))
            self.end_headers()

            self.wfile.write(tic.samples[index])

        elif self.path.startswith('/envelope/all'):
            buffer = bytearray()
            for envelope in tic.envelopes:
                buffer.extend(envelope)

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/envelope/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(ENVELOPE_SIZE))
            self.end_headers()

            self.wfile.write(tic.envelopes[index])

        elif self.path.startswith('/pattern/all'):
            buffer = bytearray()
            for pattern in tic.patterns:
                buffer.extend(pattern)

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/pattern/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(TIC_PATTERN_SIZE))
            self.end_headers()

            self.wfile.write(tic.patterns[index])

        elif self.path.startswith('/track/all'):
            buffer = bytearray()
            for track in tic.tracks:
                buffer.extend(track)

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/track/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(TIC_TRACK_SIZE))
            self.end_headers()

            self.wfile.write(tic.tracks[index])

        elif self.path.startswith('/code/all'):
            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(TIC_CODE_SIZE))
            self.end_headers()

            self.wfile.write(tic.code)

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

        elif self.path.startswith('/map/selection'):
            query = parse_qs(urlparse(self.path).query)
            sel_x = int(query['x'][0])
            sel_y = int(query['y'][0])
            sel_w = int(query['w'][0])
            sel_h = int(query['h'][0])

            for y in range(sel_y, sel_y+sel_h):
                for x in range(sel_x, sel_x+sel_w):
                    sprite = self.rfile.read(1)[0]
                    tic.map[y * TIC_MAP_WIDTH + x] = sprite

            tic.signal_update('map')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/sample/all'):
            for index in range(SFX_COUNT):
                tic.samples[index] = self.rfile.read(SAMPLE_SIZE)

            tic.signal_update('sfx')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/sample/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            tic.samples[index] = self.rfile.read(SAMPLE_SIZE)

            tic.signal_update('sfx')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/envelope/all'):
            for index in range(ENVELOPES_COUNT):
                tic.envelopes[index] = self.rfile.read(ENVELOPE_SIZE)

            tic.signal_update('sfx')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/envelope/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            tic.envelopes[index] = self.rfile.read(ENVELOPE_SIZE)

            tic.signal_update('sfx')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/pattern/all'):
            for index in range(MUSIC_PATTERNS):
                tic.patterns[index] = self.rfile.read(TIC_PATTERN_SIZE)

            tic.signal_update('music')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/pattern/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            tic.patterns[index] = self.rfile.read(TIC_PATTERN_SIZE)

            tic.signal_update('music')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/track/all'):
            for index in range(MUSIC_TRACKS):
                tic.tracks[index] = self.rfile.read(TIC_TRACK_SIZE)

            tic.signal_update('music')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/track/selected'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])

            tic.tracks[index] = self.rfile.read(TIC_TRACK_SIZE)

            tic.signal_update('music')

            self.send_response(200)
            self.end_headers()

        elif self.path.startswith('/code/all'):
            tic.code = bytearray(self.rfile.read(TIC_CODE_SIZE))

            tic.signal_update('code')

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
