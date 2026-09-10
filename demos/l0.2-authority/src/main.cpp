// L0.2 — why a container, when the binary is already self-contained?
//
// This is the obvious objection to L0. The program is a single statically
// linked file with no dependencies. You could copy it to a server and run it.
// So what is the container adding?
//
// The answer is not packaging. It is authority.
//
// A process inherits the ambient authority of whoever launched it: every file
// that user can read, every network the host can reach, every process in the
// same namespace. Nothing in the program asks for that authority and nothing
// in the program can give it up reliably — a compromised process runs with
// whatever the kernel already granted it.
//
// A container changes what the kernel grants. Same binary, same bytes, same
// digest — different authority.
//
// This program does not assert that. It measures it. It attempts a series of
// entirely ordinary actions and reports which the kernel permitted. Run it on
// a host and most succeed. Run it in the container with capabilities dropped,
// a read-only root and no network, and they fail — not because the program
// declined, but because there is nothing there to act on.
//
// Nothing here is destructive. Every probe reads, or writes to a temporary
// path, or opens a socket it immediately closes.

#include <arpa/inet.h>
#include <dirent.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>

namespace {

int allowed = 0;
int denied = 0;

void record(const char* probe, const char* detail, bool permitted, const char* why) {
    if (permitted) {
        ++allowed;
    } else {
        ++denied;
    }
    std::printf("  %-28s %-9s %s\n", probe, permitted ? "ALLOWED" : "denied",
                permitted ? detail : why);
}

// Can this process read the host's user database? On a normal system every
// user can. It is the first thing an attacker enumerates.
void probe_read_passwd() {
    std::FILE* handle = std::fopen("/etc/passwd", "r");
    if (handle == nullptr) {
        record("read /etc/passwd", "", false, "no such file — the image has no /etc");
        return;
    }
    int lines = 0;
    char line[512];
    while (std::fgets(line, sizeof(line), handle) != nullptr) {
        ++lines;
    }
    std::fclose(handle);
    char detail[128];
    std::snprintf(detail, sizeof(detail), "read %d user accounts", lines);
    record("read /etc/passwd", detail, true, "");
}

// How much filesystem is reachable at all?
void probe_list_root() {
    DIR* dir = opendir("/");
    if (dir == nullptr) {
        record("list /", "", false, "cannot open the root directory");
        return;
    }
    int entries = 0;
    while (readdir(dir) != nullptr) {
        ++entries;
    }
    closedir(dir);
    char detail[128];
    std::snprintf(detail, sizeof(detail), "%d entries visible at /", entries);
    // Two entries means "." and ".." only: an empty filesystem.
    record("list /", detail, entries > 3, "the filesystem is effectively empty");
}

// Can it reach the network? Any outbound connection is enough to exfiltrate.
void probe_network() {
    const int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        record("open a TCP socket", "", false, "socket() refused by the kernel");
        return;
    }
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(53);
    address.sin_addr.s_addr = inet_addr("1.1.1.1");

    // A non-blocking connect would be tidier; this is a demo and the timeout
    // path is what matters, so keep it simple and short.
    timeval timeout{};
    timeout.tv_sec = 3;
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    const int result = connect(sock, reinterpret_cast<sockaddr*>(&address), sizeof(address));
    close(sock);
    if (result == 0) {
        record("reach 1.1.1.1:53", "outbound connection succeeded", true, "");
    } else {
        record("reach 1.1.1.1:53", "", false, std::strerror(errno));
    }
}

// Can it persist anything? Writable storage is where a foothold is kept.
void probe_write() {
    const char* path = "/tmp/l0.2-probe";
    std::FILE* handle = std::fopen(path, "w");
    if (handle == nullptr) {
        record("write to /tmp", "", false, std::strerror(errno));
        return;
    }
    std::fputs("probe\n", handle);
    std::fclose(handle);
    unlink(path);
    record("write to /tmp", "created and removed a file", true, "");
}

// Can it start a shell? This is the difference between a bug and a breach.
void probe_shell() {
    const char* candidates[] = {"/bin/sh", "/bin/bash", "/usr/bin/sh"};
    for (const char* candidate : candidates) {
        if (access(candidate, X_OK) != 0) {
            continue;
        }
        const pid_t child = fork();
        if (child == 0) {
            // Silence the child; we only care whether exec succeeded.
            freopen("/dev/null", "w", stdout);
            freopen("/dev/null", "w", stderr);
            execl(candidate, candidate, "-c", "exit 0", nullptr);
            _exit(127);
        }
        if (child > 0) {
            int status = 0;
            waitpid(child, &status, 0);
            if (WIFEXITED(status) && WEXITSTATUS(status) != 127) {
                char detail[128];
                std::snprintf(detail, sizeof(detail), "executed %s", candidate);
                record("spawn a shell", detail, true, "");
                return;
            }
        }
    }
    record("spawn a shell", "", false, "no shell exists in this filesystem");
}

// What can this process see of the rest of the system?
void probe_processes() {
    DIR* dir = opendir("/proc");
    if (dir == nullptr) {
        record("enumerate processes", "", false, "/proc is not mounted");
        return;
    }
    int processes = 0;
    dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        if (entry->d_name[0] >= '1' && entry->d_name[0] <= '9') {
            ++processes;
        }
    }
    closedir(dir);
    char detail[128];
    std::snprintf(detail, sizeof(detail), "%d processes visible", processes);
    // A container in its own PID namespace sees only itself.
    record("enumerate processes", detail, processes > 2,
           "only this process is visible — separate PID namespace");
}

// Report the effective capability mask the kernel actually granted.
void report_capabilities() {
    std::FILE* status = std::fopen("/proc/self/status", "r");
    if (status == nullptr) {
        std::printf("  effective capabilities    : unknown (/proc not mounted)\n");
        return;
    }
    char line[512];
    std::string effective = "unknown";
    while (std::fgets(line, sizeof(line), status) != nullptr) {
        if (std::strncmp(line, "CapEff:", 7) == 0) {
            effective = std::string(line + 7);
            while (!effective.empty() && (effective.front() == ' ' || effective.front() == '\t')) {
                effective.erase(effective.begin());
            }
            while (!effective.empty() && (effective.back() == '\n' || effective.back() == ' ')) {
                effective.pop_back();
            }
        }
    }
    std::fclose(status);
    const bool none = (effective == "0000000000000000");
    std::printf("  effective capabilities    : %s%s\n", effective.c_str(),
                none ? "  (none — every capability dropped)" : "");
}

}  // namespace

int main(int argc, char** argv) {
    const bool hold = (argc > 1 && std::string(argv[1]) == "--hold");

    std::printf("L0.2 — what the kernel lets this process do\n");
    std::printf("-------------------------------------------\n");
    // The pid this process believes it has. Inside its own PID namespace it is
    // 1; the host sees an ordinary process with an ordinary pid. Both are true
    // at once, and comparing them is the clearest illustration of a namespace.
    std::printf("uid %d, gid %d, pid %d (as this process sees it)\n\n",
                getuid(), getgid(), getpid());

    report_capabilities();
    std::printf("\nProbes:\n");

    probe_read_passwd();
    probe_list_root();
    probe_network();
    probe_write();
    probe_shell();
    probe_processes();

    std::printf("\n%d allowed, %d denied\n", allowed, denied);

    if (allowed == 0) {
        std::printf(
            "\nEvery probe was denied. This is the same binary that succeeds on a\n"
            "host — the code did not change, the authority did. That difference is\n"
            "the container, and it is enforced by the kernel rather than by this\n"
            "program's good behaviour.\n");
    } else {
        std::printf(
            "\n%d probe(s) succeeded. Run this same image with:\n"
            "  --cap-drop=ALL --security-opt=no-new-privileges --read-only --network=none\n"
            "and compare. Nothing about the binary changes.\n",
            allowed);
    }

    if (hold) {
        // Stay alive so the host can be inspected while this is running:
        // ps on the host will show this process, with a different pid.
        std::printf("
Holding. Inspect from the host, then stop the container.
");
        std::fflush(stdout);
        char discard[256];
        while (std::fgets(discard, sizeof(discard), stdin) != nullptr) {
        }
    }

    // Exit code carries the count so a caller can assert on confinement.
    return allowed;
}
