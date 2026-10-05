/* wobble.app's executable (task 50): start tools/app/start, pass signals on,
 * and say so when it stops on its own.
 *
 * **Why a Mach-O and not a script.** macOS files a permission under the
 * process it holds responsible. A shell script as the bundle's executable runs
 * as /bin/sh, and the Python it starts is held responsible for itself; a
 * binary of the bundle's own is held responsible instead, and everything it
 * spawns is filed under wobble (task 48, tccd's AUTHREQ_ATTRIBUTION,
 * 2026-09-29 14:00:41 and 14:02:05).
 *
 * **Why so little.** An ad hoc grant is pinned to these exact bytes: rebuilt
 * with -O0 Accessibility went false, rebuilt as before it came back with no
 * prompt (task 48, 14:09:38 and 14:09:42). So everything that may change —
 * which Python, which flags, where the output goes — lives in tools/app/start,
 * in the repo, and a `git pull` never touches a grant. Only ROOT is baked in:
 * moving the repo means a rebuild, and asking again.
 *
 * posix_spawn and not exec: exec would make this process the Python, and the
 * Python would be held responsible for itself again. */
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <errno.h>

#ifndef ROOT
#error "build with -DROOT=\"/path/to/wobble\" (tools/build_app.py does)"
#endif
#ifndef ALERT
#define ALERT "/usr/bin/osascript"
#endif

extern char **environ;

static volatile pid_t child = 0;
static volatile sig_atomic_t passed_on = 0;

/* Logout, `killall wobble`, a Force Quit: the daemon hears it too, and quits
 * through its own door, which turns the ball's light off (task 35). */
static void pass_on(int sig) {
    passed_on = 1;
    if (child > 0) kill(child, sig);
}

/* A notifier that stopped silently is worse than none (principle 7). With no
 * terminal, the only place to say it is the screen. */
static void alert(const char *what) {
    char script[2048];
    snprintf(script, sizeof script,
             "display alert \"wobble stopped\" message \"%s What it said is in "
             ROOT "/var/app.out and in the day's log in " ROOT "/var/logs.\"", what);
    char *args[] = {ALERT, "-e", script, NULL};
    pid_t pid;
    if (posix_spawn(&pid, ALERT, NULL, NULL, args, environ) == 0) {
        int ignored;
        waitpid(pid, &ignored, 0);
    }
}

int main(int argc, char **argv) {
    char *args[argc + 1];
    args[0] = ROOT "/tools/app/start";
    for (int i = 1; i < argc; i++) args[i] = argv[i];
    args[argc] = NULL;

    struct sigaction on = {0};
    on.sa_handler = pass_on;
    sigemptyset(&on.sa_mask);
    sigaction(SIGTERM, &on, NULL);
    sigaction(SIGINT, &on, NULL);
    sigaction(SIGHUP, &on, NULL);

    pid_t pid;
    int err = posix_spawn(&pid, args[0], NULL, NULL, args, environ);
    if (err) {
        char what[512];
        snprintf(what, sizeof what, "It could not start " ROOT "/tools/app/start (%s). "
                 "If the repo moved, rebuild the app from it.", strerror(err));
        alert(what);
        return 1;
    }
    child = pid;
    if (passed_on) kill(pid, SIGTERM);   /* a signal that came before the child did */

    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno != EINTR) return 1;
    }
    if (passed_on) return WIFEXITED(status) ? WEXITSTATUS(status) : 0;
    if (WIFEXITED(status) && WEXITSTATUS(status) == 0) return 0;

    char what[256];
    if (WIFEXITED(status))
        snprintf(what, sizeof what, "It ended by itself with exit status %d.",
                 WEXITSTATUS(status));
    else
        snprintf(what, sizeof what, "It was ended by signal %d.", WTERMSIG(status));
    alert(what);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
