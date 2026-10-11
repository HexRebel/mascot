/*
    bubble.c - starts and stops the chat bubble together with mascotd

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

// Nothing of mascot may keep running once mascotd is gone. The bubble gets its
// own process group, so stopping it also stops the aichat it may be running,
// and PR_SET_PDEATHSIG covers mascotd dying without reaching bubble_stop().
// The bubble itself also quits when it loses the chat socket (shell.qml).

#define _GNU_SOURCE
#include "bubble.h"
#include "master_header.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char** environ;

static pid_t bubble_pid = -1;
static int bubble_fd = -1;
// Set by bubble_request_stop(); 0 when no stop is pending
static struct timespec stop_requested;
static bool stop_termed;

bool bubble_start(const char* command, const char* chat_socket)
{
    if (bubble_pid > 0 || !command || !*command) return false;

    // exec, so the bubble replaces the shell and inherits the death signal
    size_t length = strlen(command) + sizeof("exec ");
    char* script = malloc(length);
    if (!script) return false;
    snprintf(script, length, "exec %s", command);

    // Built before fork(): mascotd has threads, so the child may only make
    // async-signal-safe calls (no malloc, no setenv) before exec
    size_t env_count = 0;
    while (environ[env_count]) env_count++;
    char** envp = calloc(env_count + 3, sizeof(char*));
    char* socket_var = NULL;
    if (!envp || asprintf(&socket_var, "MASCOT_CHAT_SOCKET=%s", chat_socket) == -1) {
        free(envp);
        free(script);
        return false;
    }
    size_t n = 0;
    for (size_t i = 0; i < env_count; i++) {
        if (strncmp(environ[i], "MASCOT_CHAT_SOCKET=", 19) && strncmp(environ[i], "MASCOT_BUBBLE_MANAGED=", 22))
            envp[n++] = environ[i];
    }
    envp[n++] = socket_var;
    envp[n++] = "MASCOT_BUBBLE_MANAGED=1";
    char* const argv[] = { "sh", "-c", script, NULL };

    pid_t parent = getpid();
    pid_t pid = fork();
    if (pid == -1) {
        WARN("Cannot start the chat bubble: %s", strerror(errno));
        free(socket_var);
        free(envp);
        free(script);
        return false;
    }

    if (pid == 0) {
        setpgid(0, 0);
        prctl(PR_SET_PDEATHSIG, SIGTERM);
        if (getppid() != parent) _exit(0); // mascotd died before prctl()

        sigset_t none;
        sigemptyset(&none);
        sigprocmask(SIG_SETMASK, &none, NULL);

        // Quickshell logs a lot; keep it out of the terminal mascot was started from
        int devnull = open("/dev/null", O_RDWR);
        if (devnull != -1) {
            dup2(devnull, 0);
            dup2(devnull, 1);
            dup2(devnull, 2);
        }
        // mascotd's sockets and Wayland connection must not outlive it in the bubble
        close_range(3, ~0U, 0);

        execve("/bin/sh", argv, envp);
        _exit(127);
    }

    free(socket_var);
    free(envp);
    free(script);
    setpgid(pid, pid); // also from here, so bubble_stop() never races the child's setpgid()
    bubble_pid = pid;
    bubble_fd = (int)syscall(SYS_pidfd_open, pid, 0);
    INFO("Started chat bubble (pid %d): %s", pid, command);
    return true;
}

int bubble_pidfd(void)
{
    return bubble_fd;
}

// Whether the bubble has exited, without reaping it: while it is an unreaped
// zombie its process group id cannot be reused, so signalling the group is safe
static bool bubble_has_exited(siginfo_t* info)
{
    siginfo_t ignored;
    if (!info) info = &ignored;
    memset(info, 0, sizeof(*info));
    if (waitid(P_PID, bubble_pid, info, WEXITED | WNOHANG | WNOWAIT) == -1) return false;
    return info->si_pid == bubble_pid;
}

// Stops what is left of the bubble's group, then reaps the bubble
static void bubble_forget(void)
{
    kill(-bubble_pid, SIGKILL);
    waitpid(bubble_pid, NULL, 0);
    if (bubble_fd != -1) close(bubble_fd);
    bubble_fd = -1;
    bubble_pid = -1;
    stop_requested = (struct timespec){0};
    stop_termed = false;
}

void bubble_exited(void)
{
    if (bubble_pid <= 0) return;

    siginfo_t info;
    if (!bubble_has_exited(&info)) return;

    if (info.si_code == CLD_EXITED && info.si_status == 127)
        WARN("Chat bubble could not be started (command not found?); set BUBBLE_COMMAND or BUBBLE_ENABLED=false");
    else if (info.si_code == CLD_EXITED && info.si_status != 0)
        WARN("Chat bubble exited with status %d", info.si_status);
    else if (info.si_code != CLD_EXITED)
        WARN("Chat bubble was killed by signal %d", info.si_status);
    else
        INFO("Chat bubble exited");

    // Its children (an aichat answering) belong to the bubble's group
    bubble_forget();
}

// Waits up to a second for the bubble to exit, then reaps it
static bool bubble_wait(void)
{
    for (int i = 0; i < 20; i++) {
        if (bubble_has_exited(NULL)) {
            bubble_forget();
            return true;
        }
        nanosleep(&(struct timespec){ .tv_nsec = 50 * 1000 * 1000 }, NULL);
    }
    return false;
}

void bubble_stop(void)
{
    if (bubble_pid <= 0) return;

    // A connected bubble quits by itself once the chat socket is closed, after
    // unmapping its window: Hyprland 0.56 crashes when a layer surface holding
    // the keyboard dies while mapped, which is what a signal would do
    if (bubble_wait()) {
        INFO("Chat bubble quit");
        return;
    }

    kill(-bubble_pid, SIGTERM);
    if (bubble_wait()) {
        INFO("Stopped chat bubble");
        return;
    }

    WARN("Chat bubble did not stop within a second, killing it");
    bubble_forget();
}

bool bubble_running(void)
{
    return bubble_pid > 0;
}

void bubble_request_stop(void)
{
    if (bubble_pid <= 0 || stop_requested.tv_sec) return;
    clock_gettime(CLOCK_MONOTONIC, &stop_requested);
}

void bubble_tick(void)
{
    if (bubble_pid <= 0 || !stop_requested.tv_sec) return;

    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    int64_t ms = (now.tv_sec - stop_requested.tv_sec) * 1000 + (now.tv_nsec - stop_requested.tv_nsec) / 1000000;

    if (ms >= 2000) {
        WARN("Chat bubble did not stop, killing it");
        bubble_forget();
    } else if (ms >= 1000 && !stop_termed) {
        // Not connected, so it never saw the socket go away
        kill(-bubble_pid, SIGTERM);
        stop_termed = true;
    }
}
