/*
    bubble.h - starts and stops the chat bubble together with mascotd

    Copyright (C) 2026  Xedoc91

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 2
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <https://www.gnu.org/licenses/>.
*/

#ifndef BUBBLE_H
#define BUBBLE_H

#include <stdbool.h>

// Runs `sh -c "exec <command>"` in its own process group with MASCOT_CHAT_SOCKET
// set to chat_socket. Returns whether it was started
bool bubble_start(const char* command, const char* chat_socket);

// A pidfd that becomes readable when the bubble exits (add it to epoll and call
// bubble_exited()), or -1
int bubble_pidfd(void);

// Reaps the bubble after its pidfd became readable and logs how it ended
void bubble_exited(void);

// Stops the bubble's whole process group (the bubble and any aichat it runs):
// SIGTERM, then SIGKILL if it has not exited within a second
void bubble_stop(void);

#endif
