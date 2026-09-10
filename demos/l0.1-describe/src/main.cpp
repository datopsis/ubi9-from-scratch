// L0.1 — a statically linked C++ program in an image containing nothing else.
//
// Part one of the L0 tutorial. This program's job is to describe the
// environment it is running in, because that is the claim the demo makes. A
// container that prints "hello" proves it started; this one proves what it is
// running inside.
//
// It deliberately exercises the parts of C++ that pull in runtime support:
// std::string and std::vector need libstdc++, and a thrown exception needs the
// unwinder that libgcc provides. If those work in a fully static binary on an
// empty image, the linkage really is self-contained.
//
// L0.1 keeps this reporting and adds real work — SHA-256 — so the two rungs
// separate "what is in the container" from "what the container does".

#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

// Count distinct shared objects mapped into this process. A fully static
// binary maps none. /proc is supplied by the container runtime, not by the
// image, so its absence is reported rather than treated as a failure.
int count_mapped_libraries(bool& proc_available) {
    proc_available = false;
    std::FILE* maps = std::fopen("/proc/self/maps", "r");
    if (maps == nullptr) {
        return -1;
    }
    proc_available = true;

    std::vector<std::string> seen;
    char line[4096];
    while (std::fgets(line, sizeof(line), maps) != nullptr) {
        const char* slash = std::strchr(line, '/');
        if (slash == nullptr) {
            continue;
        }
        std::string entry(slash);
        while (!entry.empty() && (entry.back() == '\n' || entry.back() == ' ')) {
            entry.pop_back();
        }
        if (entry.find(".so") == std::string::npos) {
            continue;
        }
        bool already = false;
        for (const std::string& other : seen) {
            if (other == entry) { already = true; break; }
        }
        if (!already) {
            seen.push_back(entry);
        }
    }
    std::fclose(maps);
    return static_cast<int>(seen.size());
}

// Exception handling needs the unwinder, which is the part of a static C++
// link most likely to be silently missing.
bool exceptions_work() {
    try {
        throw std::runtime_error("thrown deliberately");
    } catch (const std::runtime_error& error) {
        return std::string(error.what()) == "thrown deliberately";
    } catch (...) {
        return false;
    }
}

// Report what the process can see of its own filesystem. In an image holding
// one file, almost everything a normal program expects is absent, and saying
// so concretely is more useful than asserting "the image is empty".
void report_filesystem() {
    struct Probe {
        const char* path;
        const char* what;
    };
    const Probe probes[] = {
        {"/app", "this binary"},
        {"/bin/sh", "a shell"},
        {"/etc/passwd", "user database"},
        {"/etc/resolv.conf", "DNS configuration"},
        {"/usr/lib64/libc.so.6", "a C library on disk"},
        {"/var/lib/rpm/rpmdb.sqlite", "package database"},
    };
    for (const Probe& probe : probes) {
        std::FILE* handle = std::fopen(probe.path, "r");
        const bool present = handle != nullptr;
        if (handle != nullptr) {
            std::fclose(handle);
        }
        std::printf("  %-26s %-20s %s\n", probe.path, probe.what,
                    present ? "present" : "absent");
    }
}

}  // namespace

int main(int argc, char** argv) {
    const bool wait = (argc > 1 && std::string(argv[1]) == "--wait");

    std::printf("L0.1 — static C++ on scratch\n");
    std::printf("----------------------------\n");
    std::printf("purpose              : describe the environment it runs in\n");

    std::vector<std::string> components{"libstdc++", "libgcc unwinder", "glibc"};
    std::string joined;
    for (std::size_t n = 0; n < components.size(); ++n) {
        joined += components[n];
        if (n + 1 < components.size()) {
            joined += ", ";
        }
    }
    const bool exceptions_ok = exceptions_work();
    std::printf("linked in statically : %s\n", joined.c_str());
    std::printf("exceptions           : %s\n", exceptions_ok ? "working" : "BROKEN");

    bool proc_available = false;
    const int mapped = count_mapped_libraries(proc_available);
    if (!proc_available) {
        std::printf("shared libraries     : unknown (/proc not mounted)\n");
    } else if (mapped == 0) {
        std::printf("shared libraries     : 0 — nothing loaded from the image\n");
    } else {
        std::printf("shared libraries     : %d — NOT a static build\n", mapped);
    }

    std::printf("\nWhat this container has:\n");
    report_filesystem();

    std::printf("\nThis image contains one file: the binary printing this.\n");

    if (!exceptions_ok) {
        return 1;
    }
    if (proc_available && mapped != 0) {
        return 2;
    }

    if (wait) {
        // Block so the container stays up and `podman exec` can be
        // demonstrated against it. Reading stdin avoids needing a sleep(),
        // which would mean linking more than this rung wants to.
        std::printf("\nHolding open for exec. Press Ctrl-D or stop the container to exit.\n");
        std::fflush(stdout);
        char discard[256];
        while (std::fgets(discard, sizeof(discard), stdin) != nullptr) {
            // Ignore input; the point is only to stay alive.
        }
    }
    return 0;
}
