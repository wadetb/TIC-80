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

#pragma once

#include <tic80_types.h>

typedef struct History History;
typedef struct Item Item;

typedef struct
{
	u8* buffer;
	u32 start;
	u32 end;
} Data;

typedef struct Item Item;

struct Item
{
	Item* next;
	Item* prev;

    s32 kind;
	Data data;
};

struct History
{
	Item* list;

	void* data;
	u32 size;
};

#define HISTORY_KIND_BEFORE 1
#define HISTORY_KIND_AFTER 2

History* history_create(void* data, u32 size);
void history_add(History* history);
void history_undo(History* history);
void history_redo(History* history);
void history_add_with_kind(History* history, s32 kind);
void history_undo_to_kind(History* history, s32 kind);
void history_redo_to_kind(History* history, s32 kind);
void history_delete(History* history);

