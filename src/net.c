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
	volatile u32 streamCounter;

	struct
	{
		u8* buffer;
		s32 size;
		char path[FILENAME_MAX];
	} cache;
};


typedef bool(*NetResponse)(u8* buffer, s32 size, void* data);

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
	NetResponse streamCallback;
	void *streamCallbackData;
}Request;

typedef struct
{
	char* header;
	u8* content;
	s32 contentLength;
}Response;

static Response httpRequest(Request* req)
{
	Response res = {.header = NULL, .content = NULL, .contentLength = 0};

	if(strlen(req->path) == 0)
		req->path = "/";

	{
		IPaddress ip;

		if(SDLNet_ResolveHost(&ip, req->host, req->port) >= 0)
		{
			TCPsocket sock = SDLNet_TCP_Open(&ip);

			if(sock)
			{
				SDLNet_SocketSet set = SDLNet_AllocSocketSet(1);

				if(set)
				{
					SDLNet_TCP_AddSocket(set, sock);

					{
						char header[FILENAME_MAX];
						memset(header, 0, sizeof header);
						sprintf(header, "%s %s HTTP/1.0\r\nHost: %s\r\nContent-Length: %d\r\n\r\n", req->method, req->path, req->host, req->size);
						SDLNet_TCP_Send(sock, header, (s32)strlen(header));
					}

					if(req->data && req->size)
						SDLNet_TCP_Send(sock, req->data, req->size);

					if(SDLNet_CheckSockets(set, req->timeout) == 1 && SDLNet_SocketReady(sock))
					{
						enum {Size = 4*1024+1};
						res.header = malloc(Size);

						s32 headerSize = 0;
						s32 responseSize = 0;
						s32 expectedContentLength = -1;
						s32 streamOffset = 0;

						for(;;)
						{
							s32 size = SDLNet_TCP_Recv(sock, res.header + responseSize, Size - 1);

							if(size > 0)
							{
								responseSize += size;
								res.header = realloc(res.header, responseSize + Size);

								if(headerSize == 0)
								{
									res.header[responseSize] = '\0';
									char* headerEnd = strstr((char*)res.header, "\r\n\r\n");

									if(headerEnd != NULL)
									{
										headerEnd[2] = headerEnd[3] = '\0';
										headerSize = headerEnd + 4 - res.header;

										{
											static const char ContentLength[] = "\r\nContent-Length:";

											char* start = strstr((char*)res.header, ContentLength);
											if(start)
												expectedContentLength = atoi(start + sizeof(ContentLength));
										}

										streamOffset = headerSize;
									}
								}

								if(headerSize != 0)
								{
									if(req->streamCallback)
									{
										bool wantMore = req->streamCallback(res.header + streamOffset, responseSize - streamOffset, req->streamCallbackData);
										if(!wantMore)
											break;
										streamOffset = responseSize;
									}

									if(expectedContentLength >= 0 && res.contentLength >= expectedContentLength)
										break;
								}
							}
							else break;
						}

						res.content = res.header + headerSize;
						res.contentLength = responseSize - headerSize;
					}
					
					SDLNet_FreeSocketSet(set);
				}

				SDLNet_TCP_Close(sock);
			}
		}
	}

	return res;
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
			.timeout = 3000
		};
		Response res = httpRequest(&req);

		if(res.header)
		{
			if(strstr(res.header, "200 OK"))
			{
				if(res.content && res.contentLength)
				{
					strcpy(net->cache.path, path);
					net->cache.size = res.contentLength;
					net->cache.buffer = (u8*)malloc(net->cache.size);
					memcpy(net->cache.buffer, res.content, net->cache.size);
					callback(net->cache.buffer, net->cache.size, data);
					done = true;
				}
			}

			free(res.header);
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
	Response res = httpRequest(&req);

	if(res.header)
	{
		if(strstr(res.header, "200 OK"))
		{
			callback(res.content, res.contentLength, data);
			done = true;
		}

		free(res.header);
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

static bool onGetResponse(u8* buffer, s32 size, void* data)
{
	NetGetData* netGetData = (NetGetData*)data;

	netGetData->buffer = malloc(size);
	*netGetData->size = size;
	memcpy(netGetData->buffer, buffer, size);

	return true;
}

void* netGetRequest(Net* net, const char *host, u16 port, const char* path, s32* size)
{
	NetGetData netGetData = {NULL, size};
	getRequest(net, host, port, path, onGetResponse, &netGetData);

	return netGetData.buffer;
}

static bool onPutResponse(u8* buffer, s32 size, void* data)
{
	return true;
}

void netPutRequest(Net* net, const char *host, u16 port, const char* path, void *data, s32 size)
{
	putRequest(net, host, port, path, data, size, onPutResponse);
}

typedef struct
{
	Net *net;
	s32 counter;
	Request req;
}NetStreamData;

bool netStreamCallback(u8* buffer, s32 size, void* data)
{
	NetStreamData* stream = (NetStreamData*)data;

	printf("%.*s", size, (char*)buffer);

	return stream->net->streamCounter == stream->counter;
}

int SDLCALL netStreamThread(void *data)
{
	NetStreamData* stream = (NetStreamData*)data;

	while(stream->net->streamCounter == stream->counter)
		httpRequest(&stream->req);
}

void netGetStream(Net* net, const char *host, u16 port, const char* path)
{
	NetStreamData* stream = (NetStreamData*)malloc(sizeof(NetStreamData));

	net->streamCounter++; // Any prior stream thread will now exit gracefully

	stream->net = net;
	stream->counter = net->streamCounter;

	stream->req = (Request){
		.host = host,
		.port = port,
		.method = "GET",
		.path = path,
		.timeout = 3000,
		.streamCallback = netStreamCallback,
		.streamCallbackData = stream,
	};

	SDL_Thread *thread = SDL_CreateThread(netStreamThread, "stream thread", stream);
	SDL_DetachThread(thread);
}

Net* createNet()
{
	SDLNet_Init();

	Net* net = (Net*)malloc(sizeof(Net));

	*net = (Net)
	{
		.streamCounter = 0,

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