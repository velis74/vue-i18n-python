"""Tests for the message-set checker."""

from .messages import check_messages, flatten, resolves
from .report import Severity

BASE = {
    "cart": {"count": "{n} items", "none": "no items", "label": "Cart"},
    "greet": "Hello @:cart.label",
}


def kinds(report) -> list[str]:  # noqa: ANN001 - a Report, but importing it here buys nothing
    return [problem.kind for problem in report.problems]


def test_a_clean_set_reports_nothing() -> None:
    assert not check_messages({"en": BASE, "sl": dict(BASE)}).problems


def test_flatten_produces_the_paths_a_caller_would_write() -> None:
    assert flatten(BASE) == {
        "cart.count": "{n} items",
        "cart.none": "no items",
        "cart.label": "Cart",
        "greet": "Hello @:cart.label",
    }


def test_flatten_keeps_a_flat_dotted_key_as_written() -> None:
    """vue-i18n accepts both shapes in one resource, so both have to come out."""
    assert flatten({"a.b": "flat", "a": {"c": "nested"}}) == {"a.b": "flat", "a.c": "nested"}


def test_resolves_agrees_with_the_runtime_on_both_shapes() -> None:
    assert resolves({"a": {"b": "x"}}, "a.b")
    assert resolves({"a.b": "x"}, "a.b")
    assert not resolves({"a": {"b": "x"}}, "a.c")


def test_a_message_that_does_not_compile_is_an_error() -> None:
    report = check_messages({"en": {"bad": "unbalanced }"}})
    assert kinds(report) == ["does-not-compile"]
    problem = report.problems[0]
    assert problem.severity is Severity.ERROR
    # The compiler's column is inside the message, so it must not masquerade as a file coordinate.
    assert problem.line is None
    assert problem.column is None
    assert problem.in_message == 12


def test_a_link_to_nothing_is_an_error() -> None:
    report = check_messages({"en": {"a": "see @:nowhere"}})
    assert kinds(report) == ["broken-link"]


def test_a_link_satisfied_by_another_locale_is_only_a_warning() -> None:
    """Links resolve through the fallback chain, which this checker is not told about."""
    report = check_messages({"en": {"brand": "Acme", "a": "@:brand"}, "sl": {"a": "@:brand"}}, base_locale="en")
    assert "broken-link" not in kinds(report)
    assert "link-needs-fallback" in kinds(report)


def test_a_dynamic_link_is_not_reported() -> None:
    """`@:{section}` cannot be followed statically, and guessing would produce a false alarm."""
    report = check_messages({"en": {"a": "@:{section}"}})
    assert "broken-link" not in kinds(report)


def test_an_unknown_modifier_warns_but_a_built_in_one_does_not() -> None:
    clean = check_messages({"en": {"x": "Hi", "a": "@.upper:x"}})
    assert "unknown-modifier" not in kinds(clean)

    odd = check_messages({"en": {"x": "Hi", "a": "@.shout:x"}})
    assert "unknown-modifier" in kinds(odd)


def test_more_plural_forms_than_the_built_in_rule_can_reach_warns() -> None:
    """The signature surprise of this library: `min(choice, 2)` stops at the third form."""
    report = check_messages({"en": {"trips": "none | one | two | few | many"}})
    assert "unreachable-plural-form" in kinds(report)

    fine = check_messages({"en": {"trips": "none | one | many"}})
    assert "unreachable-plural-form" not in kinds(fine)


def test_a_key_missing_from_one_locale_is_named_with_that_locale() -> None:
    report = check_messages({"en": {"a": "A", "b": "B"}, "sl": {"a": "A"}}, base_locale="en")
    missing = [problem for problem in report.problems if problem.kind == "missing-key"]
    assert [(problem.locale, problem.key) for problem in missing] == [("sl", "b")]


def test_a_key_only_one_locale_has_is_reported_as_extra() -> None:
    report = check_messages({"en": {"a": "A"}, "sl": {"a": "A", "z": "Z"}}, base_locale="en")
    extra = [problem for problem in report.problems if problem.kind == "extra-key"]
    assert [(problem.locale, problem.key) for problem in extra] == [("sl", "z")]


def test_the_base_locale_defaults_to_en_when_present() -> None:
    report = check_messages({"sl": {"a": "A"}, "en": {"a": "A", "b": "B"}})
    assert [problem.locale for problem in report.problems if problem.kind == "missing-key"] == ["sl"]


def test_a_non_string_leaf_is_left_alone() -> None:
    """A resource can carry numbers or nulls; they are not messages and do not compile."""
    assert not check_messages({"en": {"n": 3, "nothing": None}}).problems
