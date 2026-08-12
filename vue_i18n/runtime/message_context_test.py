"""Tests for the message context's own decisions, as opposed to what it renders.

Rendering is covered end to end by `conformance/render.json`. What is left here is the handful of
places where the context has to decide something on its own.
"""

from .message_context import MessageContext, MessageContextOptions, plural_default


def _ctx(**kwargs) -> MessageContext:
    return MessageContext(MessageContextOptions(locale="sl", **kwargs))


def test_an_out_of_range_plural_rule_clamps_rather_than_raising() -> None:
    """DEVIATION, and a deliberate one - see PROGRESS.md.

    vue-i18n reads `messages[index]`, gets `undefined` and throws `UNEXPECTED_RETURN_TYPE`. This
    port clamps to the last form. The case is not hypothetical: a hand-written south-Slavic rule
    that returns index 4 for a four-form Slovene message does exactly this.
    """
    forms = ["nič", "ena", "dve", "veliko"]
    ctx = _ctx(plural_index=5, plural_rules={"sl": lambda _c, _l, _o=None: 4})
    assert ctx.plural(forms) == "veliko"

    # And in the other direction, since a rule is arbitrary caller code.
    assert _ctx(plural_index=1, plural_rules={"sl": lambda _c, _l, _o=None: -3}).plural(forms) == "nič"


def test_a_rule_returning_a_non_index_falls_back_to_the_built_in_rule() -> None:
    ctx = _ctx(plural_index=1, plural_rules={"sl": lambda _c, _l, _o=None: "nonsense"})
    assert ctx.plural(["ena", "veliko"]) == "ena"


def test_no_forms_at_all_is_the_empty_string() -> None:
    assert _ctx(plural_index=1).plural([]) == ""


def test_the_built_in_rule_is_vue_i18ns_and_ignores_the_locale() -> None:
    """Two forms are singular/plural; three or more clamp at index 2, in every language."""
    assert [plural_default(n, 2) for n in (0, 1, 2, 5)] == [1, 0, 1, 1]
    assert [plural_default(n, 3) for n in (0, 1, 2, 5, 105)] == [0, 1, 2, 2, 2]
    assert [plural_default(n, 5) for n in (3, 5, 105)] == [2, 2, 2]


def test_a_custom_rule_may_take_two_arguments_or_three() -> None:
    """Upstream passes the built-in rule as a third argument; a two-argument rule must still work."""
    two = _ctx(plural_index=9, plural_rules={"sl": lambda _c, _l: 0})
    three = _ctx(plural_index=9, plural_rules={"sl": lambda _c, _l, _o: 0})
    assert two.plural(["a", "b"]) == "a"
    assert three.plural(["a", "b"]) == "a"
