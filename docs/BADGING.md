# Repository badges

Badges are compact links to evidence, not claims. The README uses only badges
maintained by GitHub, OpenSSF, Shields.io, or a factual static project label,
and every badge links to a page where a contributor can inspect the underlying
result.

## Badge inventory

| Badge | Evidence and destination | Maintenance |
| --- | --- | --- |
| License | Repository-detected licence; links to `LICENSE`. | GitHub/Shields derives it from repository content. |
| Base: Red Hat UBI 9 | Factual statement that the reconstruction targets the UBI 9 family; links to Red Hat's UBI documentation. | Update manually only if the target family changes. |
| Subject: ubi9-micro | Factual statement of the image under dissection; links to the method that pins and acquires it. | Update manually only if the subject changes. |
| Status: investigation | Factual project-stage label; links to the roadmap that defines the stage. | Update manually when the stage changes. |
| Badge policy | Links to this inventory. | Update with any badge change. |

## Deliberately absent

CI, CodeQL, OpenSSF Scorecard, and release badges are not present because the
workflows and releases that would back them do not exist in this repository
yet. Adding a badge before its evidence exists produces a badge that reports
nothing, which is exactly what this policy is meant to prevent. Add each one
in the same pull request that adds its workflow, and record it above.

## Source markup

The canonical badge markup lives at the top of `README.md`. When changing it:

1. use HTTPS for both the image and destination;
2. link workflow badges to the workflow page, not to a single run;
3. keep repository coordinates explicit as `datopsis/ubi9-from-scratch`;
4. URL-encode static badge labels and values;
5. preview links while signed out so badges do not depend on private
   credentials; and
6. update this inventory in the same pull request.

Do not add download counts, stars, "production ready", vulnerability-free,
compliance, coverage, or passing badges without stable machine-verifiable
evidence. Do not expose tokens through custom badge endpoints.

This repository additionally must not carry any badge implying that its
reconstruction is supported by, endorsed by, or equivalent to a Red Hat
product.

References:

- [GitHub workflow status badges](https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge)
- [Shields.io GitHub badges](https://shields.io/badges)
- [Red Hat Universal Base Images](https://developers.redhat.com/products/rhel/ubi)
