// MIT License

// Copyright (c) 2017 Vadim Grigoruk @nesbox // grigoruk@gmail.com

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#include "net.h"
#include "tic.h"
#include "SDL_net.h"

#include <stdlib.h>
#include <stdio.h>

struct Net
{
	struct
	{
		u8* buffer;
		s32 size;
		char path[FILENAME_MAX];
	} cache;
};


typedef void(*NetResponse)(u8* buffer, s32 size, void* data);

#if defined(__EMSCRIPTEN__)

static void getRequest(Net* net, const char* path, NetResponse callback, void* data)
{
	callback(NULL, 0, data);
}

#else

static void netClearCache(Net* net)
{
	if(net->cache.buffer)
		free(net->cache.buffer);

	net->cache.buffer = NULL;
	net->cache.size = 0;
	memset(net->cache.path, 0, sizeof net->cache.path);
}

typedef struct
{
	const char *host;
	u16 port;
	const char *method;
	const char *path;
	u8 *data;
	s32 size;
	s32 timeout;
}Request;

typedef struct
{
	u8* data;
	s32 size;
}Buffer;

static Buffer httpRequest(Request* req)
{
	Buffer buffer = {.data = NULL, .size = 0};

	if (strlen(req->path) == 0)
		req->path = "/";

	{
		IPaddress ip;

		if (SDLNet_ResolveHost(&ip, req->host, req->port) >= 0)
		{
			TCPsocket sock = SDLNet_TCP_Open(&ip);

			if (sock)
			{
				SDLNet_SocketSet set = SDLNet_AllocSocketSet(1);

				if(set)
				{
					SDLNet_TCP_AddSocket(set, sock);

					{
						char header[FILENAME_MAX];
						memset(header, 0, sizeof header);
						sprintf(header, "%s %s HTTP/1.0\r\nHost: " TIC_HOST "\r\nContent-Length: %d\r\n\r\n", req->method, req->path, req->size);
						SDLNet_TCP_Send(sock, header, (s32)strlen(header));
						if(req->data && req->size)
							SDLNet_TCP_Send(sock, req->data, req->size);
					}

					if(SDLNet_CheckSockets(set, req->timeout) == 1 && SDLNet_SocketReady(sock))
					{
						enum {Size = 4*1024+1};
						buffer.data = malloc(Size);
						s32 size = 0;

						for(;;)
						{
							size = SDLNet_TCP_Recv(sock, buffer.data + buffer.size, Size-1);

							if(size > 0)
							{
								buffer.size += size;
								buffer.data = realloc(buffer.data, buffer.size + Size);
							}
							else break;
						}

						buffer.data[buffer.size] = '\0';
					}
					
					SDLNet_FreeSocketSet(set);
				}

				SDLNet_TCP_Close(sock);
			}
		}
	}

	return buffer;
}

static void getRequest(Net* net, const char *host, u16 port, const char* path, NetResponse callback, void* data)
{
	if(strcmp(host, TIC_HOST) == 0 && port == 80 && strcmp(net->cache.path, path) == 0)
	{
		callback(net->cache.buffer, net->cache.size, data);
	}
	else
	{
		netClearCache(net);

		bool done = false;

		Request req = {
			.host = host,
			.port = port,
			.method = "GET",
			.path = path,
			.data = NULL,
			.size = 0,
			.timeout = 3000
		};
		Buffer buffer = httpRequest(&req);

		if(buffer.data && buffer.size)
		{
			if(strstr((char*)buffer.data, "200 OK"))
			{
				s32 contentLength = 0;

				{
					static const char ContentLength[] = "Content-Length:";

					char* start = strstr((char*)buffer.data, ContentLength);

					if(start)
						contentLength = atoi(start + sizeof(ContentLength));
				}

				static const char Start[] = "\r\n\r\n";
				u8* start = (u8*)strstr((char*)buffer.data, Start);

				if(start)
				{
					strcpy(net->cache.path, path);
					net->cache.size = contentLength ? contentLength : buffer.size - (s32)(start - buffer.data);
					net->cache.buffer = (u8*)malloc(net->cache.size);
					memcpy(net->cache.buffer, start + sizeof Start - 1, net->cache.size);
					callback(net->cache.buffer, net->cache.size, data);
					done = true;
				}
			}

			free(buffer.data);
		}

		if(!done)
			callback(NULL, 0, data);
	}
}

static void putRequest(Net* net, const char *host, u16 port, const char* path, void* data, s32 dataSize, NetResponse callback)
{
	netClearCache(net);

	bool done = false;

	Request req = {
		.host = host,
		.port = port,
		.method = "PUT",
		.path = path,
		.data = data,
		.size = dataSize,
		.timeout = 3000
	};
	Buffer buffer = httpRequest(&req);

	if(buffer.data && buffer.size)
	{
		if(strstr((char*)buffer.data, "200 OK"))
		{
			s32 contentLength = 0;

			{
				static const char ContentLength[] = "Content-Length:";

				char* start = strstr((char*)buffer.data, ContentLength);

				if(start)
					contentLength = atoi(start + sizeof(ContentLength));
			}

			static const char Start[] = "\r\n\r\n";
			u8* start = (u8*)strstr((char*)buffer.data, Start);

			if(start)
			{
				strcpy(net->cache.path, path);
				net->cache.size = contentLength ? contentLength : buffer.size - (s32)(start - buffer.data);
				net->cache.buffer = (u8*)malloc(net->cache.size);
				memcpy(net->cache.buffer, start + sizeof Start - 1, net->cache.size);
				callback(net->cache.buffer, net->cache.size, data);
				done = true;
			}
		}

		free(buffer.data);
	}

	if(!done)
		callback(NULL, 0, data);
}

#endif

typedef struct
{
	void* buffer;
	s32* size;
} NetGetData;

static void onGetResponse(u8* buffer, s32 size, void* data)
{
	NetGetData* netGetData = (NetGetData*)data;

	netGetData->buffer = malloc(size);
	*netGetData->size = size;
	memcpy(netGetData->buffer, buffer, size);
}

void* netGetRequest(Net* net, const char *host, u16 port, const char* path, s32* size)
{
	NetGetData netGetData = {NULL, size};
	getRequest(net, host, port, path, onGetResponse, &netGetData);

	return netGetData.buffer;
}

static void onPutResponse(u8* buffer, s32 size, void* data)
{
}

void netPutRequest(Net* net, const char *host, u16 port, const char* path, void *data, s32 size)
{
	putRequest(net, host, port, path, data, size, onPutResponse);
}

Net* createNet()
{
	SDLNet_Init();

	Net* net = (Net*)malloc(sizeof(Net));

	*net = (Net)
	{
		.cache = 
		{
			.buffer = NULL,
			.size = 0,
			.path = {0},
		},
	};

	return net;
}

void closeNet(Net* net)
{
	free(net);
	
	SDLNet_Quit();
}