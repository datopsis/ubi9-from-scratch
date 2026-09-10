/* L0.0 — the payload is deliberately trivial.
 *
 * This rung is about the anatomy of a container image, not about the program
 * inside it. The program exists only so the image has exactly one file to find
 * when you take the archive apart by hand.
 *
 * It is C rather than C++ so that the binary is as close to the floor of a
 * static glibc link as it can be. Even printing one line costs the better part
 * of a megabyte once libc is linked in, which is itself worth noticing: the
 * cost is glibc, not your code.
 */

#include <stdio.h>

int main(void) {
    puts("L0.0 — anatomy");
    puts("--------------");
    puts("I am the only file in this image.");
    puts("");
    puts("Take the image apart with:");
    puts("  podman save --format docker-archive -o l0.0.tar l0.0-anatomy:9.8");
    puts("  tar -tvf l0.0.tar");
    puts("");
    puts("Everything else you can see at runtime was added by the container");
    puts("runtime, not by the image. That distinction is the lesson.");
    return 0;
}
