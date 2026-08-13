"""What actually ends up in the artefact.

Everything else in this suite reads the source tree. A wheel is not the source tree: it is whatever
hatch decided to put in, and the difference is invisible until someone installs the package. So this
builds a real wheel and reads its member list.

That is not hypothetical caution. The wheel target inherited no `exclude`, so every release would
have carried eleven `*_test.py` files into users' `site-packages` — where they cannot even run,
because the corpora they read are not in the wheel.

Skipped, not failed, when `build` is missing: a contributor without the dev extra should still get a
green suite. `pyproject.toml` lists `build` under `dev` for this test alone.
"""

import zipfile

from pathlib import Path

import pytest

build = pytest.importorskip("build", reason="`pip install -e .[dev]` provides it; see this module's docstring")

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wheel_members(tmp_path_factory: pytest.TempPathFactory) -> frozenset[str]:
    """Build a wheel from the real project and return the names it contains.

    Module-scoped because building is the slow part of this file by a wide margin, and every test
    below asks a different question of the same artefact.
    """
    out = tmp_path_factory.mktemp("wheel")
    builder = build.ProjectBuilder(REPO_ROOT)
    path = builder.build("wheel", str(out))
    with zipfile.ZipFile(path) as archive:
        return frozenset(archive.namelist())


def test_the_wheel_carries_no_tests(wheel_members: frozenset[str]) -> None:
    """Tests sit beside the code they cover, so only the build config keeps them out of the wheel."""
    shipped = sorted(name for name in wheel_members if name.endswith("_test.py"))
    assert shipped == [], f"tests leaked into the wheel: {shipped}"


def test_the_runtime_is_complete(wheel_members: frozenset[str]) -> None:
    """A missing module is the failure this catches; the list is what `import vue_i18n` needs."""
    for module in (
        "vue_i18n/__init__.py",
        "vue_i18n/compiler/parser.py",
        "vue_i18n/compiler/tokenizer.py",
        "vue_i18n/runtime/context.py",
        "vue_i18n/runtime/translate.py",
        "vue_i18n/runtime/message_context.py",
        "vue_i18n/plurals/__init__.py",
        "vue_i18n/plurals/_generated.py",
    ):
        assert module in wheel_members, f"{module} is missing from the wheel"


def test_the_typing_marker_ships(wheel_members: frozenset[str]) -> None:
    """`py.typed` is a file, not a flag: absent from the artefact, the package reads as untyped."""
    assert "vue_i18n/py.typed" in wheel_members


def test_the_licence_ships(wheel_members: frozenset[str]) -> None:
    """MIT requires the notice to travel with the code, and hatch places it under `.dist-info`."""
    assert any(name.endswith("licenses/LICENSE") for name in wheel_members)
