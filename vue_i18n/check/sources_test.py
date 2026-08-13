"""Tests for the source scanner and the code-against-messages check."""

from .report import Severity
from .sources import check_sources, extract_from_python, extract_from_text

MESSAGES = {"en": {"cart": {"count": "{n} items", "label": "Cart"}}}


def test_python_calls_are_found_with_the_key_at_the_right_argument() -> None:
    """`translate(ctx, key)` puts the key second; a `t(key)` wrapper puts it first."""
    uses = extract_from_python('translate(ctx, "a.b")\nt("c.d")\n', "x.py")
    assert [(use.key, use.line) for use in uses] == [("a.b", 1), ("c.d", 2)]


def test_a_method_call_counts_as_the_same_function() -> None:
    uses = extract_from_python('i18n.t("a.b")', "x.py")
    assert [use.key for use in uses] == ["a.b"]


def test_a_computed_key_is_recorded_rather_than_guessed_at() -> None:
    uses = extract_from_python('translate(ctx, f"item.{kind}")', "x.py")
    assert [use.key for use in uses] == [None]


def test_a_file_that_does_not_parse_yields_nothing_instead_of_raising() -> None:
    assert extract_from_python("def (:", "x.py") == []


def test_script_calls_are_found_in_a_vue_file() -> None:
    source = "<template>\n  {{ $t('a.b') }}\n</template>\n<script>t(\"c.d\")</script>\n"
    uses = extract_from_text(source, "X.vue")
    assert [(use.key, use.line) for use in uses] == [("a.b", 2), ("c.d", 4)]
    assert all(use.approximate for use in uses)


def test_a_commented_out_call_is_skipped_without_moving_the_lines_after_it() -> None:
    """Comments are blanked rather than removed, so later findings keep their real line numbers."""
    source = "<!-- $t('gone') -->\n// $t('also.gone')\n/* $t('block') */\n$t('real')\n"
    uses = extract_from_text(source, "X.vue")
    assert [(use.key, use.line) for use in uses] == [("real", 4)]


def test_a_template_literal_with_a_substitution_is_dynamic() -> None:
    uses = extract_from_text("t(`item.${kind}`)", "X.ts")
    assert [use.key for use in uses] == [None]


def test_a_word_ending_in_t_is_not_a_translation_call() -> None:
    """Without the lookbehind, `format(` and `split(` would both match."""
    assert extract_from_text('format("a")\nx.split("b")\n', "X.ts") == []


def test_an_unknown_key_is_an_error_and_a_known_one_is_not() -> None:
    uses = extract_from_python('translate(ctx, "cart.label")\ntranslate(ctx, "cart.emty")\n', "x.py")
    report = check_sources(uses, MESSAGES, report_unused=False)
    assert [(problem.kind, problem.key) for problem in report.problems] == [("unknown-key", "cart.emty")]
    assert report.problems[0].severity is Severity.ERROR


def test_a_key_present_in_any_locale_counts_as_known() -> None:
    """The fallback chain is what makes a key defined only in the base locale usable elsewhere."""
    uses = extract_from_python('translate(ctx, "only.in.en")', "x.py")
    report = check_sources(uses, {"en": {"only": {"in": {"en": "x"}}}, "sl": {}}, report_unused=False)
    assert not report.errors


def test_a_dynamic_key_is_a_note_not_an_error() -> None:
    uses = extract_from_python("translate(ctx, key)", "x.py")
    report = check_sources(uses, MESSAGES, report_unused=False)
    assert [problem.severity for problem in report.problems] == [Severity.NOTE]


def test_unused_keys_are_reported_when_every_key_could_be_seen() -> None:
    uses = extract_from_python('translate(ctx, "cart.label")', "x.py")
    report = check_sources(uses, MESSAGES)
    assert [problem.key for problem in report.problems if problem.kind == "unused-key"] == ["cart.count"]


def test_unused_reporting_is_suppressed_once_a_key_is_computed() -> None:
    """A dynamic key can reach anything, so "nothing asks for it" stops being a claim worth making."""
    uses = extract_from_python('translate(ctx, "cart.label")\ntranslate(ctx, key)\n', "x.py")
    report = check_sources(uses, MESSAGES)
    assert "unused-key" not in [problem.kind for problem in report.problems]
