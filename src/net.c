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

#include <stdlib.h>
#include <stdio.h>

#include <curl/curl.h>
#include "../3rd-party/sdl2/include/SDL.h"

struct Net
{
	struct Curl_easy* curl;
};

typedef struct
{
    void* buffer;
    s32 size;
} CurlData;

static size_t writeCallback(void *contents, size_t size, size_t nmemb, void *userp)
{
	CurlData* data = (CurlData*)userp;

	const size_t total = size * nmemb;
	data->buffer = realloc(data->buffer, data->size + total);
	memcpy((u8*)data->buffer + data->size, contents, total);
	data->size += total;

	return total;
}

void* netGetRequest(Net* net, const char* url, s32* size)
{
	CurlData data = {NULL, 0};

	if(net->curl)
	{
		curl_easy_setopt(net->curl, CURLOPT_URL, url);
		curl_easy_setopt(net->curl, CURLOPT_WRITEDATA, &data);

		if(curl_easy_perform(net->curl) != CURLE_OK)
			return NULL;
	}

	*size = data.size;

    return data.buffer;
}

static size_t readCallback(void *contents, size_t size, size_t nmemb, void *userp)
{
	CurlData* data = (CurlData*)userp;

	size_t total = MIN(size * nmemb, data->size);

	memcpy((u8*)contents, data->buffer, total);

	data->buffer += total;
	data->size -= total;

	return total;
}

void netPutRequest(Net* net, const char *url, void *content, s32 size)
{
	CurlData data = {content, size};

	struct Curl_easy* curl = curl_easy_init();

	struct curl_slist *headers = NULL;

	char contentLength[1024];
	snprintf(contentLength, sizeof(contentLength), "Content-Length: %d", size);
  	headers = curl_slist_append(headers, contentLength);
 	headers = curl_slist_append(headers, "Expect:");
 	headers = curl_slist_append(headers, "Transfer-Encoding:");

	curl_easy_setopt(curl, CURLOPT_PUT, 1);
	curl_easy_setopt(curl, CURLOPT_URL, url);
	curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
	curl_easy_setopt(curl, CURLOPT_READFUNCTION, readCallback);
	curl_easy_setopt(curl, CURLOPT_READDATA, &data);
	curl_easy_setopt(curl, CURLOPT_INFILESIZE, size);

	curl_easy_perform(curl);

	curl_slist_free_all(headers);

	curl_easy_cleanup(curl);
}

typedef struct
{
	bool cancel;
	char url[FILENAME_MAX];
	NetResponse callback;
	void* data;
}NetStreamData;

size_t streamCallback(char *ptr, size_t size, size_t nmemb, void *userdata)
{
	NetStreamData* stream = (NetStreamData*)userdata;

	size_t total = size * nmemb;
	
	if(stream->callback)
	{
		if(!stream->callback(ptr, total, stream->data))
		{
			stream->cancel = true;
			return 0;
		}
	}

	return total;
}

int SDLCALL netStreamThread(void *data)
{
	NetStreamData* stream = (NetStreamData*)data;

	struct Curl_easy* curl = curl_easy_init();

	curl_easy_setopt(curl, CURLOPT_URL, stream->url);
	curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, streamCallback);
	curl_easy_setopt(curl, CURLOPT_WRITEDATA, stream);

	while(!stream->cancel)
	{
		if(curl_easy_perform(curl) != CURLE_OK)
			SDL_Delay(1000);
	}

	curl_easy_cleanup(curl);

	free(stream);
}

void netGetStream(Net* net, const char *url, NetResponse callback, void* data)
{
	NetStreamData* stream = (NetStreamData*)malloc(sizeof(NetStreamData));

	if(stream)
	{
		*stream = (NetStreamData)
		{
			.cancel = false,
			.callback = callback,
			.data = data
		};

		snprintf(stream->url, sizeof(stream->url), "%s", url);

		SDL_Thread *thread = SDL_CreateThread(netStreamThread, "stream thread", stream);
		if(thread)
			SDL_DetachThread(thread);
	}
}

Net* createNet()
{
	Net* net = (Net*)malloc(sizeof(Net));

	*net = (Net)
	{
		.curl = curl_easy_init()
	};

	curl_easy_setopt(net->curl, CURLOPT_WRITEFUNCTION, writeCallback);

	return net;
}

void closeNet(Net* net)
{
	if(net->curl)
		curl_easy_cleanup(net->curl);

	free(net);
}
