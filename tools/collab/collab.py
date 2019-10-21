import http.server
import socketserver

from urllib.parse import urlparse, parse_qs

PORT = 8000

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


class TIC:
    def __init__(self):
        self.tiles = [bytearray(b'\0' * (TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE)) 
                      for _ in range(TIC_BANK_SPRITES * TIC_SPRITE_BANKS)]
        self.palette = bytearray(b'\0' * TIC_PALETTE_SIZE * TIC_PALETTE_CHANNELS)

    def set_pixel(self, x, y, color):
        tile_x = x // TIC_SPRITESIZE
        tile_y = y // TIC_SPRITESIZE
        tile_index = tile_y * TIC_SPRITESHEET_COLS + tile_x
        tile = tic.tiles[tile_index]
        tile_stride = TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE
        x_in_tile = x - (tile_x * TIC_SPRITESIZE)
        y_in_tile = y - (tile_y * TIC_SPRITESIZE)
        tile_offset = y_in_tile * tile_stride + x_in_tile * TIC_PALETTE_BPP // BITS_IN_BYTE
        if x_in_tile & 1:
            tile[tile_offset] = (tile[tile_offset] & 0x0f) | (color << 4)
        else:
            tile[tile_offset] = (tile[tile_offset] & 0xf0) | color

    def get_pixel(self, x, y):
        tile_x = x // TIC_SPRITESIZE
        tile_y = y // TIC_SPRITESIZE
        tile_index = tile_y * TIC_SPRITESHEET_COLS + tile_x
        tile = tic.tiles[tile_index]
        tile_stride = TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE
        x_in_tile = x - (tile_x * TIC_SPRITESIZE)
        y_in_tile = y - (tile_y * TIC_SPRITESIZE)
        tile_offset = y_in_tile * tile_stride + x_in_tile * TIC_PALETTE_BPP // BITS_IN_BYTE
        if x_in_tile & 1:
            return (tile[tile_offset] >> 4) & 0x0f
        else:
            return tile[tile_offset]  & 0x0f

    def set_palette(self, buffer):
        self.palette = buffer

    def get_palette(self):
        return self.palette

tic = TIC()

class CollabHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.end_headers()
            self.wfile.write("welcome to collab :)".encode())

        elif self.path.startswith('/sprite/all'):
            buffer = bytearray(b'\0' * (TIC_SPRITES * TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE))

            for y in range(TIC_SPRITES * TIC_SPRITESIZE * TIC_SPRITESIZE // TIC_SPRITESHEET_SIZE):
                for x in range(TIC_SPRITESHEET_SIZE):
                    color = tic.get_pixel(x, y)
                    buffer_offset = (y * TIC_SPRITESHEET_SIZE + x) * TIC_PALETTE_BPP // BITS_IN_BYTE
                    buffer[buffer_offset] |= color << (TIC_PALETTE_BPP if x & 1 else 0)

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        elif self.path.startswith('/sprite/single'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])
            size = int(query['size'][0])

            buffer = bytearray(b'\0' * (size * size * TIC_PALETTE_BPP // BITS_IN_BYTE))

            start_y, start_x = divmod(index, TIC_SPRITESHEET_COLS)

            for y in range(size):
                for x in range(size):                  
                    color = tic.get_pixel(start_x * TIC_SPRITESIZE + x, start_y * TIC_SPRITESIZE + y)
                    buffer_offset = (y * size + x) * TIC_PALETTE_BPP // BITS_IN_BYTE
                    buffer[buffer_offset] |= color << (TIC_PALETTE_BPP if x & 1 else 0)

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        if self.path.startswith('/palette'):
            buffer = tic.get_palette()

            self.send_response(200)
            self.send_header('Content-Length', '{}'.format(len(buffer)))
            self.end_headers()

            self.wfile.write(buffer)

        else:
            self.send_response(400)
            self.end_headers()


    def do_PUT(self):
        if self.path.startswith('/sprite/all'):
            buffer = self.rfile.read(TIC_SPRITES * TIC_SPRITESIZE * TIC_SPRITESIZE * TIC_PALETTE_BPP // BITS_IN_BYTE)

            for y in range(TIC_SPRITES * TIC_SPRITESIZE * TIC_SPRITESIZE // TIC_SPRITESHEET_SIZE):
                for x in range(TIC_SPRITESHEET_SIZE):
                    buffer_offset = (y * TIC_SPRITESHEET_SIZE + x) * TIC_PALETTE_BPP // BITS_IN_BYTE
                    color = (buffer[buffer_offset] >> (TIC_PALETTE_BPP if x & 1 else 0)) & 0x0f
                    tic.set_pixel(x, y, color)

            self.send_response(200)
            self.end_headers()

        if self.path.startswith('/sprite/single'):
            query = parse_qs(urlparse(self.path).query)
            index = int(query['index'][0])
            size = int(query['size'][0])

            buffer = self.rfile.read(size * size * TIC_PALETTE_BPP // BITS_IN_BYTE)

            tile_y, tile_x = divmod(index, TIC_SPRITESHEET_COLS)
            
            for y in range(size):
                for x in range(size):
                    buffer_offset = (y * size + x) * TIC_PALETTE_BPP // BITS_IN_BYTE
                    color = (buffer[buffer_offset] >> (TIC_PALETTE_BPP if x & 1 else 0)) & 0x0f
                    tic.set_pixel(tile_x * TIC_SPRITESIZE + x, tile_y * TIC_SPRITESIZE + y, color)

            self.send_response(200)
            self.end_headers()

        if self.path.startswith('/palette'):
            buffer = self.rfile.read(TIC_PALETTE_SIZE * TIC_PALETTE_CHANNELS)
            tic.set_palette(buffer)

            self.send_response(200)
            self.end_headers()

        else:
            self.send_response(400)
            self.end_headers()

try:
    server = http.server.HTTPServer(('localhost', PORT), CollabHandler)
    print('Started http server')
    server.serve_forever()
except KeyboardInterrupt:
    print('^C received, shutting down server')
    server.socket.close()
