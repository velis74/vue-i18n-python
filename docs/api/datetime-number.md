# datetime and number

vue-i18n's `d()` and `n()`. Both need the `intl` extra:

```sh
pip install "vue-i18n-python[intl]"
```

```python
from vue_i18n import datetime as d, number as n
```

::: warning These do not match `Intl` character for character
Everything *around* the format is a port: the argument shapes, the named formats, the fallback walk,
the missing handling, the override merging and the cache. The formatting itself cannot be —
`Intl.DateTimeFormat` and `Intl.NumberFormat` do not exist in Python, so `babel` stands in, and the
two carry different CLDR data versions.

Month names and separators may differ from the browser. If a string must be byte-identical on both
ends, format it on one end and send it.
:::

## Named formats

Declare them on the context, the same objects a Vue application passes:

```python
ctx = create_core_context(
    locale="sl",
    fallback_locale="en",
    number_formats={
        "sl": {"currency": {"style": "currency", "currency": "EUR"}},
        "en": {"currency": {"style": "currency", "currency": "GBP"}},
    },
    datetime_formats={
        "sl": {"short": {"year": "numeric", "month": "short", "day": "numeric"}},
    },
)

n(ctx, 1234.5, "currency")      # '1.234,50 €'
d(ctx, moment, "short")         # '12. avg. 2026'
```

A named format is looked up through the fallback chain, so a format defined only in `en` is found
from an `sl` context.

## Call shapes

```python
n(ctx, 1234.5)                                   # locale defaults
n(ctx, 1234.5, "currency")                       # a named format
n(ctx, 1234.5, "currency", "en")                 # named format, explicit locale
n(ctx, 1234.5, "currency", {"currency": "GBP"})  # named format with overrides
n(ctx, 1234.5, {"style": "percent"})             # options, no named format
```

`d()` takes the same shapes. Its value may be a `datetime`, a `date`, a POSIX timestamp **in
milliseconds** (as `Date` does), or an ISO 8601 string.

## Options that are honoured

**Numbers** — `style` (`decimal`, `percent`, `currency`), `currency`, `useGrouping`,
`minimumIntegerDigits`, `minimumFractionDigits`, `maximumFractionDigits`, `notation: "compact"` with
`compactDisplay`.

**Dates** — `dateStyle` and `timeStyle` (`full`, `long`, `medium`, `short`), the component options
`era`, `year`, `month`, `day`, `weekday`, `hour`, `minute`, `second`, `timeZoneName`, plus `hour12`
and `timeZone`.

The component options are mapped onto a CLDR skeleton, which is what babel takes — so
`{"year": "numeric", "month": "short", "day": "numeric"}` becomes `yMMMd`. That mapping is what lets
a format object written for a Vue front end be read here unchanged.

## Options that are ignored

Accepted and then dropped, because babel has nowhere to put them:

- **numbers** — `localeMatcher`, `currencySign`, `signDisplay`, `unit`, `unitDisplay`,
  `roundingMode`, `roundingPriority`, `roundingIncrement`, `trailingZeroDisplay`,
  `minimumSignificantDigits`, `maximumSignificantDigits`
- **dates** — `localeMatcher`, `formatMatcher`, `calendar`, `numberingSystem`, `hourCycle`,
  `fractionalSecondDigits`

Ask rather than discover:

```python
from vue_i18n.runtime.number import unsupported_number_options
from vue_i18n.runtime.datetime import unsupported_datetime_options

unsupported_number_options({"style": "decimal", "signDisplay": "always"})   # {'signDisplay'}
```

## Not supported

`part=True` (`formatToParts`) raises `NotImplementedError`. babel has no counterpart, and a caller
asking for parts wants the structure — an approximation would be worse than a refusal.

## Missing formats

Same as `translate`: a format name that resolves nowhere returns the name, or `NOT_RESOLVED` when
the context was built with `unresolving=True`. A non-numeric value to `n()` warns and returns the
empty string rather than raising, which is upstream's behaviour.
