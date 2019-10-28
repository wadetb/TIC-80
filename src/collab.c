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

#include "collab.h"
#include "studio.h"

#define MAX_COLLAB_BLOCKS 3

typedef struct
{
	s32 offset;
	s32 size;
	s32 count;
} CollabBlock;

struct Collab
{
	CollabBlock blocks[MAX_COLLAB_BLOCKS];
	u8* changedBits[MAX_COLLAB_BLOCKS];
	bool anyChanged;
};

struct Collab* collab_create(s32 offset0, s32 size0, s32 count0, s32 offset1, s32 size1, s32 count1, s32 offset2, s32 size2, s32 count2)
{
	Collab* collab = (Collab*)malloc(sizeof(Collab));

	collab->blocks[0].offset = offset0;
	collab->blocks[0].size = size0;
	collab->blocks[0].count = count0;
	collab->blocks[1].offset = offset1;
	collab->blocks[1].size = size1;
	collab->blocks[1].count = count1;
	collab->blocks[2].offset = offset2;
	collab->blocks[2].size = size2;
	collab->blocks[2].count = count2;

	collab->changedBits[0] = (u8*)malloc(BITARRAY_SIZE(count0));
	collab->changedBits[1] = (u8*)malloc(BITARRAY_SIZE(count1));
	collab->changedBits[2] = (u8*)malloc(BITARRAY_SIZE(count2));

	memset(collab->changedBits[0], 0, BITARRAY_SIZE(count0));
	memset(collab->changedBits[1], 0, BITARRAY_SIZE(count1));
	memset(collab->changedBits[2], 0, BITARRAY_SIZE(count2));

	collab->anyChanged = false;

	return collab;
}

void collab_delete(Collab* collab)
{
	free(collab->changedBits[0]);
	free(collab->changedBits[1]);
	free(collab->changedBits[2]);
}

void collab_diff(Collab* collab, tic_mem* tic)
{
	collab->anyChanged = false;

	for(s32 i = 0; i < MAX_COLLAB_BLOCKS; i++)
	{
		CollabBlock* block = &collab->blocks[i];

		u8* cart = (u8*)&tic->cart + block->offset;
		u8* server = (u8*)&tic->collab + block->offset;

		for(s32 index = 0; index < block->count; index++)
		{
			bool diff = memcmp(cart, server, block->size);

			if(diff)
				collab->anyChanged = true;

			tic_tool_poke1(collab->changedBits[i], index, diff);

			cart += block->size;
			server += block->size;
		}
	}
}

void* collab_data(Collab *collab, tic_mem *tic, s32 block, s32 index)
{
    s32 offset = collab->blocks[block].offset;
    s32 size = collab->blocks[block].size * collab->blocks[block].count;
    return (u8*)&tic->collab + offset;
}

bool collab_isChanged(Collab* collab, s32 block, s32 index)
{
	return tic_tool_peek1(collab->changedBits[block], index);
}

void collab_setChanged(Collab* collab, s32 block, s32 index, u8 value)
{
	tic_tool_poke1(collab->changedBits[block], index, value);
}

bool collab_anyChanged(Collab* collab)
{
	return collab->anyChanged;
}

void collab_fetch(Collab* collab, tic_mem* tic)
{
	for (s32 i = 0; i < MAX_COLLAB_BLOCKS; i++)
	{
		if(collab->blocks[i].count)
		{
			s32 offset = collab->blocks[i].offset;
			s32 size = collab->blocks[i].size * collab->blocks[i].count;
			u8* data = (u8*)&tic->collab + offset;

			char url[1024];
			snprintf(url, sizeof(url), "/data?offset=%d&size=%d", offset, size);
			getCollabData(url, data, size);
		}
	}
}

void collab_put(Collab* collab, tic_mem* tic)
{
	for (s32 i = 0; i < MAX_COLLAB_BLOCKS; i++)
	{
		if(collab->blocks[i].count)
		{
			s32 offset = collab->blocks[i].offset;
			s32 size = collab->blocks[i].size * collab->blocks[i].count;
			u8* data = (u8*)&tic->cart + offset;

			char url[1024];
			snprintf(url, sizeof(url), "/data?offset=%d&size=%d", offset, size);
			putCollabData(url, data, size);
		}
	}
}

void collab_get(Collab* collab, tic_mem* tic)
{
	for (s32 i = 0; i < MAX_COLLAB_BLOCKS; i++)
	{
		if(collab->blocks[i].count)
		{
			s32 offset = collab->blocks[i].offset;
			s32 size = collab->blocks[i].size * collab->blocks[i].count;
			u8* data = (u8*)&tic->cart + offset;

			char url[1024];
			snprintf(url, sizeof(url), "/data?offset=%d&size=%d", offset, size);
			getCollabData(url, data, size);
		}
	}
}

void collab_putRange(Collab* collab, tic_mem* tic, s32 block, s32 first, s32 count)
{
    CollabBlock* bl = &collab->blocks[block];

    if(bl->count)
    {
        s32 offset = bl->offset + first * bl->size;
        s32 size = count * bl->size;
        u8* data = (u8*)&tic->cart + offset;

        char url[1024];
        snprintf(url, sizeof(url), "/data?offset=%d&size=%d", offset, size);
        putCollabData(url, data, size);
    }
}

void collab_getRange(Collab* collab, tic_mem* tic, s32 block, s32 first, s32 count)
{
    CollabBlock* bl = &collab->blocks[block];

    if(bl->count)
    {
        s32 offset = bl->offset + first * bl->size;
        s32 size = count * bl->size;
        u8* data = (u8*)&tic->cart + offset;

        char url[1024];
        snprintf(url, sizeof(url), "/data?offset=%d&size=%d", offset, size);
        getCollabData(url, data, size);
    }
}
