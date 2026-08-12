"""i18n-united — the vue-i18n message format and runtime, in Python.

The short version::

    from i18n_united import create_core_context, translate

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
arguably wrong — see ``i18n_united.plurals`` for the one place that is worth knowing about.
"""

__version__ = "0.1.0"


def __getattr__(name: str):  # noqa: ANN202 - a module-level __getattr__ has no useful return type
    """Re-export the public surface lazily.

    Importing eagerly here would make ``import i18n_united`` pull in the compiler and the whole
    runtime, and would create a cycle: ``runtime.context`` reads ``__version__`` from this module.
    """
    if name in _PUBLIC:
        module_name, attribute = _PUBLIC[name]
        from importlib import import_module

        return getattr(import_module(module_name, __name__), attribute)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_PUBLIC = {
    "create_core_context": (".runtime.context", "create_core_context"),
    "CoreContext": (".runtime.context", "CoreContext"),
    "translate": (".runtime.translate", "translate"),
    "NOT_RESOLVED": (".runtime.context", "NOT_RESOLVED"),
    "I18nWarning": (".runtime.warnings", "I18nWarning"),
    "create_parser": (".compiler.parser", "create_parser"),
    "CompileError": (".compiler.errors", "CompileError"),
}

__all__ = ["__version__", *_PUBLIC]
