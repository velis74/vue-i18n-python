# Upstream reports

Things found in vue-i18n while porting it, written up for the maintainers.

Both were found by reading `core-base` closely enough to port it, and both were reproduced against
the real published packages before being written down. Neither is speculative.

| | Status |
|---|---|
| `report-1-fallback-cache.md` | Filed as [intlify/vue-i18n#2562](https://github.com/intlify/vue-i18n/issues/2562) |
| `report-2-escapeparams.md` | **Not filed.** Private security advisory; see below |
| `report-3-fallback-simple-map.md` | **Not filed.** Public issue, ready to send |

The `repro-*.mjs` scripts reproduce them. Run from the repository
root; both print the version of the package they actually used.

## Why report 2 is not in this repository

It is a gap in an XSS mitigation and has not been disclosed. `vendor/vue-i18n/SECURITY.md` asks for
private reporting through
[the Security tab](https://github.com/intlify/vue-i18n/security/advisories/new), and committing an
unfixed vulnerability report to a repository that may become public is disclosure by another route.

The write-up **and its reproduction script** are therefore listed in `.gitignore` - a working
proof of concept is disclosure just as much as the prose is. Remove that line once the advisory has been filed and
upstream has released a fix, and commit it then — the write-up is worth keeping alongside the port
that found it, and `i18n_united/runtime/sanitize.py` refers to the same gap.
