// L0 — the floor: a statically linked C++ program in an image with nothing else.
//
// The program does real work: it computes the SHA-256 of standard input and
// prints the digest. That function is deliberate. Every rung of the ladder
// computes the same digest by a different route — here from a self-contained
// implementation, at L2 through OpenSSL, at L3 through OpenSSL's FIPS provider
// — so the rungs produce identical output and their sizes are directly
// comparable. The cost of each requirement is then the difference in bytes,
// not a difference in what the program does.
//
// SHA-256 is implemented here rather than linked because L0's whole claim is
// that the image contains nothing but the binary. Pulling in a crypto library
// would make the point untestable.
//
// It also self-tests against the NIST vectors on every run, and exits non-zero
// if they fail, so CI gates on correctness rather than on the process starting.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

// FIPS 180-4, section 4.2.2 — the first 32 bits of the fractional parts of the
// cube roots of the first 64 primes.
const std::uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

inline std::uint32_t rotr(std::uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
}

class Sha256 {
  public:
    Sha256() { reset(); }

    void reset() {
        // Fractional parts of the square roots of the first 8 primes.
        h_[0] = 0x6a09e667; h_[1] = 0xbb67ae85;
        h_[2] = 0x3c6ef372; h_[3] = 0xa54ff53a;
        h_[4] = 0x510e527f; h_[5] = 0x9b05688c;
        h_[6] = 0x1f83d9ab; h_[7] = 0x5be0cd19;
        length_ = 0;
        buffered_ = 0;
    }

    void update(const unsigned char* data, std::size_t size) {
        length_ += static_cast<std::uint64_t>(size) * 8;
        while (size > 0) {
            const std::size_t take = (64 - buffered_ < size) ? 64 - buffered_ : size;
            std::memcpy(block_ + buffered_, data, take);
            buffered_ += take;
            data += take;
            size -= take;
            if (buffered_ == 64) {
                compress(block_);
                buffered_ = 0;
            }
        }
    }

    std::string hex() {
        // Pad: 0x80, then zeros, then the 64-bit big-endian bit length.
        unsigned char pad[72] = {0x80};
        const std::size_t pad_len = (buffered_ < 56) ? 56 - buffered_ : 120 - buffered_;
        const std::uint64_t bits = length_;
        update(pad, pad_len);

        unsigned char tail[8];
        for (int i = 0; i < 8; ++i) {
            tail[i] = static_cast<unsigned char>((bits >> (56 - 8 * i)) & 0xff);
        }
        update(tail, 8);
        // length_ is now meaningless: the padding and length field were fed
        // through update() and counted. This object is single-use.

        static const char* digits = "0123456789abcdef";
        std::string out;
        out.reserve(64);
        for (int i = 0; i < 8; ++i) {
            for (int shift = 24; shift >= 0; shift -= 8) {
                const unsigned char byte = (h_[i] >> shift) & 0xff;
                out += digits[byte >> 4];
                out += digits[byte & 0x0f];
            }
        }
        return out;
    }

  private:
    void compress(const unsigned char* p) {
        std::uint32_t w[64];
        for (int i = 0; i < 16; ++i) {
            w[i] = (static_cast<std::uint32_t>(p[i * 4]) << 24) |
                   (static_cast<std::uint32_t>(p[i * 4 + 1]) << 16) |
                   (static_cast<std::uint32_t>(p[i * 4 + 2]) << 8) |
                   static_cast<std::uint32_t>(p[i * 4 + 3]);
        }
        for (int i = 16; i < 64; ++i) {
            const std::uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
            const std::uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }

        std::uint32_t a = h_[0], b = h_[1], c = h_[2], d = h_[3];
        std::uint32_t e = h_[4], f = h_[5], g = h_[6], h = h_[7];

        for (int i = 0; i < 64; ++i) {
            const std::uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            const std::uint32_t ch = (e & f) ^ (~e & g);
            const std::uint32_t t1 = h + S1 + ch + K[i] + w[i];
            const std::uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            const std::uint32_t t2 = S0 + maj;
            h = g; g = f; f = e; e = d + t1;
            d = c; c = b; b = a; a = t1 + t2;
        }

        h_[0] += a; h_[1] += b; h_[2] += c; h_[3] += d;
        h_[4] += e; h_[5] += f; h_[6] += g; h_[7] += h;
    }

    std::uint32_t h_[8];
    std::uint64_t length_;
    unsigned char block_[64];
    std::size_t buffered_;
};

std::string sha256_of(const std::string& input) {
    Sha256 hash;
    hash.update(reinterpret_cast<const unsigned char*>(input.data()), input.size());
    return hash.hex();
}

// FIPS 180-4 test vectors. If these fail the implementation is wrong and the
// program must not report a digest as if it were trustworthy.
bool self_test() {
    struct Vector {
        const char* input;
        const char* expected;
    };
    const Vector vectors[] = {
        {"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        {"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
        {"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
         "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"},
    };
    for (const Vector& vector : vectors) {
        if (sha256_of(vector.input) != vector.expected) {
            std::fprintf(stderr, "SELF-TEST FAILED for input of length %zu\n",
                         std::strlen(vector.input));
            return false;
        }
    }
    return true;
}

// Count distinct shared objects mapped into this process. A fully static
// binary maps none. /proc is supplied by the container runtime, not the image,
// so its absence is reported rather than treated as failure.
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

}  // namespace

int main(int argc, char** argv) {
    const bool report = (argc > 1 && std::string(argv[1]) == "--report");

    if (!self_test()) {
        return 1;
    }

    if (!report) {
        // Do the actual work: hash standard input, print the digest.
        Sha256 hash;
        unsigned char buffer[65536];
        std::size_t got;
        while ((got = std::fread(buffer, 1, sizeof(buffer), stdin)) > 0) {
            hash.update(buffer, got);
        }
        std::printf("%s\n", hash.hex().c_str());
        return 0;
    }

    // --report: describe the runtime instead, for the demo's own claims.
    std::printf("L0 — static C++ on scratch\n");
    std::printf("--------------------------\n");
    std::printf("function             : SHA-256 of stdin (self-contained)\n");
    std::printf("NIST self-test       : passed (3 vectors)\n");
    std::printf("sha256(\"abc\")        : %s\n", sha256_of("abc").c_str());

    // Exceptions need the unwinder, the part of a static C++ link most likely
    // to be missing.
    bool exceptions_ok = false;
    try {
        throw std::runtime_error("thrown deliberately");
    } catch (const std::runtime_error&) {
        exceptions_ok = true;
    } catch (...) {
    }
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

    std::printf("\nThis image contains one file: the binary you are reading this from.\n");

    if (!exceptions_ok) {
        return 1;
    }
    if (proc_available && mapped != 0) {
        return 2;
    }
    return 0;
}
