"""Tests for `python -m vue_i18n.check`, with the exit codes a build actually branches on."""

import json

from pathlib import Path

import pytest

from .__main__ import main

EN = {"cart": {"label": "Cart", "count": "{n} items"}}
SL = {"cart": {"label": "Košarica"}}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A message set whose translation is behind, which is the normal state of a real project."""
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.json").write_text(json.dumps(EN), encoding="utf-8")
    (locales / "sl.json").write_text(json.dumps(SL), encoding="utf-8")
    (tmp_path / "app.py").write_text('translate(ctx, "cart.label")\n', encoding="utf-8")
    return tmp_path


def test_an_unfinished_translation_does_not_fail_the_build(project: Path, capsys) -> None:
    """The whole point of the split: `sl` missing a key is work in flight, not a broken commit."""
    assert main([str(project / "locales"), "--source", str(project / "app.py")]) == 0
    assert "cart.count: in en, not in sl" in capsys.readouterr().out


def test_a_key_missing_from_the_base_locale_fails(project: Path, capsys) -> None:
    (project / "app.py").write_text('translate(ctx, "cart.nope")\n', encoding="utf-8")
    assert main([str(project / "locales"), "--source", str(project / "app.py")]) == 1
    assert "'cart.nope' is not in en" in capsys.readouterr().out


def test_a_key_only_a_translation_has_fails_and_says_where_it_was_found(project: Path, capsys) -> None:
    """Present in `sl`, absent from `en`, is the base locale being incomplete - an error."""
    (project / "locales" / "sl.json").write_text(
        json.dumps({"cart": {"label": "Košarica", "promo": "Akcija"}}), encoding="utf-8"
    )
    (project / "app.py").write_text('translate(ctx, "cart.promo")\n', encoding="utf-8")
    assert main([str(project / "locales"), "--source", str(project / "app.py")]) == 1
    out = capsys.readouterr().out
    assert "missing from the base locale en" in out
    assert "(found in sl)" in out


def test_strict_makes_an_unfinished_translation_fatal(project: Path) -> None:
    assert main([str(project / "locales"), "--source", str(project / "app.py"), "--strict"]) == 1


def test_the_base_locale_can_be_something_other_than_en(project: Path, capsys) -> None:
    """With `sl` as the source language, `en` is the one that may lag."""
    assert main([str(project / "locales"), "--base-locale", "sl"]) == 1
    assert "cart.count: in sl, missing from the base locale sl" not in capsys.readouterr().out


def test_a_clean_set_says_so_and_exits_zero(tmp_path: Path, capsys) -> None:
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.json").write_text('{"a": "A"}', encoding="utf-8")
    assert main([str(locales)]) == 0
    assert "nothing to report" in capsys.readouterr().out


def test_malformed_json_is_reported_with_its_position_not_a_traceback(project: Path, capsys) -> None:
    (project / "locales" / "broken.json").write_text('{"a": ', encoding="utf-8")
    assert main([str(project / "locales")]) == 2
    assert "broken.json:" in capsys.readouterr().err


def test_a_base_locale_that_is_not_there_is_refused_rather_than_assumed(project: Path, capsys) -> None:
    assert main([str(project / "locales"), "--base-locale", "de"]) == 2
    assert "not among en, sl" in capsys.readouterr().err


def test_no_message_files_is_a_usage_error_not_a_pass(tmp_path: Path) -> None:
    """Exit 2, never 0 - a misconfigured path must not read as a green build."""
    assert main([str(tmp_path)]) == 2


def test_json_output_is_parseable_and_carries_counts(project: Path, capsys) -> None:
    (project / "app.py").write_text('translate(ctx, "cart.nope")\n', encoding="utf-8")
    main([str(project / "locales"), "--source", str(project / "app.py"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["error"] == 1
    unknown = [problem for problem in payload["problems"] if problem["kind"] == "unknown-key"]
    assert [(problem["key"], problem["line"]) for problem in unknown] == [("cart.nope", 1)]


def test_github_output_is_one_workflow_command_per_line(project: Path, capsys) -> None:
    (project / "app.py").write_text('translate(ctx, "cart.nope")\n', encoding="utf-8")
    main([str(project / "locales"), "--source", str(project / "app.py"), "--format", "github", "--quiet"])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith("::error file=")
    assert all(line.startswith("::") for line in lines)
