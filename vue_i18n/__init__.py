"""vue-i18n-python — the vue-i18n message format and runtime, in Python.

The short version::

    from vue_i18n import create_core_context, translate

    ctx = create_core_context(
        locale="sl",
        fallback_locale="en",
        messages={"sl": {"hello": "Zdravo {name}"}, "en": {"hello": "Hello {name}"}},
    )
    translate(ctx, "hello", {"name": "Jure"})   # 'Zdravo Jure'

The message files are ordinary vue-i18n resources — the same JSON a Vue front end loads, with
``{named}`` placeholders, ``a | b | c`` plurals, ``@:linked`` messages and ``@.upper:`` modifiers.

Option names are vue-i18n's, in snake_case: ``fallbackLocale`` is ``fallback_locale``,
``missingWarn`` is ``missing_warn``. Behaviour is vue-i18n's too, including where vue-i18n is
arguably wrong — see ``vue_i18n.plurals`` for the one place that is worth knowing about.
"""

__version__ = "0.1.0"


def __getattr__(name: str):  # noqa: ANN202 - a module-level __getattr__ has no useful return type
    """Re-export the public surface lazily.

    Importing eagerly here would make ``import vue_i18n`` pull in the compiler and the whole
    runtime, and would create a cycle: ``runtime.context`` reads ``__version__`` from this module.
    """
    if name in _PUBLIC:
        module_name, attribute = _PUBLIC[name]
        from importlib import import_module

        return getattr(import_module(module_name, __name__), attribute)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_PUBLIC = {
    # The context and the three calls made against it - the whole of ordinary use.
    "create_core_context": (".runtime.context", "create_core_context"),
    "CoreContext": (".runtime.context", "CoreContext"),
    "translate": (".runtime.translate", "translate"),
    "datetime": (".runtime.datetime", "datetime"),
    "number": (".runtime.number", "number"),
    # Changing the fallback after the fact, which has to go through here or the chain cache
    # answers with the old one.
    "update_fallback_locale": (".runtime.context", "update_fallback_locale"),
    "fallback_with_locale_chain": (".runtime.fallbacker", "fallback_with_locale_chain"),
    "fallback_with_simple": (".runtime.fallbacker", "fallback_with_simple"),
    # Sentinels and the warning category, both of which a caller compares against or filters on.
    "NOT_RESOLVED": (".runtime.context", "NOT_RESOLVED"),
    "I18nWarning": (".runtime.warnings", "I18nWarning"),
    # Parsing a message without rendering it - rarely needed, but the alternative is reaching into
    # a private module.
    "create_parser": (".compiler.parser", "create_parser"),
    "CompileError": (".compiler.errors", "CompileError"),
}

__all__ = ["__version__", *_PUBLIC]
