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

#include "history.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static void list_delete(Item* list, Item* from)
{
	Item* it = from;

	while(it)
	{
		Item* next = it->next;

		if(it->data.buffer) free(it->data.buffer);
		if(it) free(it);

		it = next;
	}
}

static Item* list_insert(Item* list, s32 kind, Data* data)
{
	Item* item = (Item*)malloc(sizeof(Item));
	item->next = NULL;
	item->prev = NULL;
	item->kind = kind;
	item->data = *data;

	if(list)
	{
		list_delete(list, list->next);

		list->next = item;
		item->prev = list;
	}

	return item;
}

static Item* list_first(Item* list)
{
	Item* it = list;
	while(it->prev) it = it->prev;

	return it;
}

History* history_create(void* data, u32 size)
{
	History* history = (History*)malloc(sizeof(History));
	history->data = data;

	history->list = NULL;
	history->size = size;

	Data initial;
	initial.start = 0;
	initial.end = size;
	initial.buffer = (u8*)malloc(size);
	memcpy(initial.buffer, data, size);

	history->list = list_insert(history->list, 0, &initial);

	return history;
}

void history_delete(History* history)
{
	if(history)
	{
		list_delete(history->list, list_first(history->list));

		free(history);
	}
}

static void history_apply(History* history, Data* data)
{
	for (u32 i = data->start, k = 0; i < data->end; ++i, ++k)
		((u8*)history->data)[i] = data->buffer[k];
}

void history_print(History* history)
{
	printf("<<< HISTORY %p >>>>\n", history);

	static const char* kinds[] = {"NONE", "BEFORE", "AFTER"};

	Item* item = history->list;
	for(; item->prev != NULL; item = item->prev)
		;

	int i = 0;
	for(; item != NULL; item = item->next, i++)
		printf("%d: %s %d-%d %s\n", i, item == history->list ? ">>>" : "", 
			item->data.start, item->data.end, kinds[item->kind]);
}

void history_add_with_kind(History* history, s32 kind)
{
	printf("=== BEFORE ADD TO HISTORY %p ===\n", history);
	history_print(history);

	{
		Data data;

		data.start = 0;
		data.end = history->size;
		// for(data.start = 0; data.start < history->size; data.start++)
		// 	if(history->state[data.start] != ((u8*)history->data)[data.start])
		// 		break;
		// for(data.end = history->size - 1; data.end > 0; data.end--)
		// 	if(history->state[data.end] != ((u8*)history->data)[data.end])
		// 		break;
		// data.end++;

		if(data.start < data.end)
		{
			u32 size = data.end - data.start;
			data.buffer = malloc(size);

			memcpy(data.buffer, (u8*)history->data + data.start, size);
		}
		else
		{
			data.buffer = NULL;
		}

		history->list = list_insert(history->list, kind, &data);
	}

	printf("=== AFTER ADD TO HISTORY %p ===\n", history);
	history_print(history);
}

void history_add(History* history)
{
	history_add_with_kind(history, 0);
}

void history_undo_to_kind(History* history, s32 kind)
{
	printf("=== BEFORE UNDO HISTORY %p ===\n", history);
	history_print(history);

	while(history->list->prev)
	{
		history->list = history->list->prev;
		history_apply(history, &history->list->data);
		if(history->list->kind == kind)
			break;
	}

	printf("=== AFTER UNDO HISTORY %p ===\n", history);
	history_print(history);
}

void history_undo(History* history)
{
	history_undo_to_kind(history, 0);
}

void history_redo_to_kind(History* history, s32 kind)
{
	printf("=== BEFORE REDO HISTORY %p ===\n", history);
	history_print(history);

	while(history->list->next)
	{
		history->list = history->list->next;
		history_apply(history, &history->list->data);
		if(history->list->kind == kind)
			break;
	}

	printf("=== AFTER REDO HISTORY %p ===\n", history);
	history_print(history);
}

void history_redo(History* history)
{
	history_redo_to_kind(history, 0);
}
