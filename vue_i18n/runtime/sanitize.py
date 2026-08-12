"""HTML escaping for interpolated parameters.

Partial port of ``packages/shared/src/sanitize.ts``.

``escape_parameter`` exists because a Vue application can render a translated string as HTML, at
which point a value interpolated into it is an injection point. Upstream does two things when the
option is on: it escapes the *parameters* going in, and it sanitizes the *result* coming out.

Only the first is ported. :func:`escape_html` below is upstream's ``escapeHtml``, character for
character. Upstream's ``sanitizeTranslatedHtml`` — attribute-value sanitisation, event-handler
neutralisation and `javascript:` URL stripping — is not ported yet, and
:func:`warn_output_not_sanitized` says so out loud the first time a context enables the option,
because a security feature that is quietly weaker than the one it copies is worse than one that is
plainly absent.
"""

import warnings

from .warnings import I18nWarning

_warned = False


def escape_html(raw_text: str) -> str:
    """Upstream's ``escapeHtml``. The ``&`` must go first or the later replacements double-escape."""
    return (
        raw_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
        # `/` closes a tag and `=` opens an attribute; both are escaped for the same reason.
        .replace("/", "&#x2F;")
        .replace("=", "&#x3D;")
    )


def warn_output_not_sanitized() -> None:
    """Say once, per process, that the output half of ``escape_parameter`` is not ported."""
    global _warned
    if _warned:
        return
    _warned = True
    warnings.warn(
        "escape_parameter escapes interpolated values, but this port does not yet apply "
        "vue-i18n's sanitizeTranslatedHtml to the rendered result. Do not rely on it to make an "
        "untrusted message safe to render as HTML.",
        I18nWarning,
        stacklevel=2,
    )
