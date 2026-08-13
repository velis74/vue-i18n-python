"""Tests for `runtime/context.py`, the port of `core-base/src/context.ts`."""

from pathlib import Path

from .. import __version__, VUE_I18N_VERSION
from .context import create_core_context


def test_context_version_reports_the_vue_i18n_release_not_this_package() -> None:
    """Upstream defaults the field to `core-base`'s own `VERSION`, so it answers "which vue-i18n".

    The two numbers are deliberately different things: `__version__` identifies this package and
    moves on its own schedule, `VUE_I18N_VERSION` names the release the port behaves like. Reporting
    the former here would leave a caller comparing against a vue-i18n version with nothing to read.
    """
    assert create_core_context().version == VUE_I18N_VERSION
    assert create_core_context().version != __version__


def test_an_explicit_version_wins() -> None:
    """`options.version` is honoured, exactly as `isString(options.version)` does upstream."""
    assert create_core_context(version="9.9.9").version == "9.9.9"


def test_a_non_string_version_falls_back_to_the_default() -> None:
    """Upstream normalises rather than raising, and every option in this file follows that."""
    assert create_core_context(version=11).version == VUE_I18N_VERSION  # type: ignore[arg-type]
    assert create_core_context(version=None).version == VUE_I18N_VERSION


def test_the_tracked_version_matches_the_submodule_pin() -> None:
    """`VUE_I18N_VERSION` is a claim about `vendor/vue-i18n`; UPSTREAM.md records the same number.

    Kept honest here rather than by reading the submodule, because a shallow checkout - CI, an
    sdist, a user's clone without `--recurse-submodules` - has no tags to ask.
    """
    upstream_md = (Path(__file__).resolve().parents[2] / "UPSTREAM.md").read_text(encoding="utf-8")
    assert f"v{VUE_I18N_VERSION}" in upstream_md
