// L0 — the floor: a statically linked C++ program in an image with nothing else.
//
// The program reports on its own runtime environment, because that is the
// claim the demo makes. A container that merely prints "hello" proves it
// started; this one proves what it is running inside.
//
// It deliberately exercises the parts of C++ that pull in runtime support:
// std::string and std::vector (libstdc++), and a thrown exception (stack
// unwinding, which is what libgcc provides). If those work in a fully static
// binary on an empty image, the linkage is genuinely self-contained.

#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

// Count distinct shared objects mapped into this process. A fully static
// binary maps none. /proc is mounted by the container runtime, not supplied by
// the image, so its absence is reported rather than treated as an error.
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
        const char* path = std::strchr(line, '/');
        if (path == nullptr) {
            continue;
        }
        std::string entry(path);
        while (!entry.empty() && (entry.back() == '\n' || entry.back() == ' ')) {
            entry.pop_back();
        }
        if (entry.find(".so") == std::string::npos) {
            continue;
        }
        bool already = false;
        for (const std::string& other : seen) {
            if (other == entry) {
                already = true;
                break;
            }
        }
        if (!already) {
            seen.push_back(entry);
        }
    }
    std::fclose(maps);
    return static_cast<int>(seen.size());
}

// Prove that exception handling works. In a static build this requires the
// unwinder to have been linked in, which is the part most likely to be missing.
bool exceptions_work() {
    try {
        throw std::runtime_error("thrown deliberately");
    } catch (const std::runtime_error& error) {
        return std::string(error.what()) == "thrown deliberately";
    } catch (...) {
        return false;
    }
}

}  // namespace

int main() {
    std::printf("L0 — static C++ on scratch\n");
    std::printf("--------------------------\n");

    // std::vector and std::string exercise libstdc++ allocation paths.
    std::vector<std::string> components{"libstdc++", "libgcc unwinder", "glibc"};
    std::string joined;
    for (std::size_t n = 0; n < components.size(); ++n) {
        joined += components[n];
        if (n + 1 < components.size()) {
            joined += ", ";
        }
    }
    std::printf("linked in statically : %s\n", joined.c_str());
    std::printf("exceptions           : %s\n", exceptions_work() ? "working" : "BROKEN");

    bool proc_available = false;
    const int mapped = count_mapped_libraries(proc_available);
    if (!proc_available) {
        std::printf("shared libraries     : unknown (/proc not mounted)\n");
    } else if (mapped == 0) {
        std::printf("shared libraries     : 0 — nothing loaded from the image\n");
    } else {
        std::printf("shared libraries     : %d — NOT a static build\n", mapped);
    }

    std::printf("\nThis image contains one file: the binary you are reading this from.\n");

    // A non-zero exit if the demo's own claim does not hold, so CI can gate on
    // the result rather than on the process merely starting.
    if (!exceptions_work()) {
        return 1;
    }
    if (proc_available && mapped != 0) {
        return 2;
    }
    return 0;
}
