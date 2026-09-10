# Reconstruction

How the from-scratch build is assembled.

> [!NOTE]
> Not started. This document records the build once the dissection has
> established what the build is supposed to produce.

The reconstruction is constrained by the same property that defines the
subject: the resulting image contains no package manager, so every file in it
must be placed by a build container writing into an `--installroot`, and the
image itself is assembled from that directory over `scratch`.

The build must state, for each choice it makes, whether the choice is dictated
by the dissection or is an assumption made in the absence of evidence.
