# Message format

The format is vue-i18n's, unchanged. This page is a reference for what a message can contain and
what it does here; [vue-i18n's own syntax documentation](https://vue-i18n.intlify.dev/guide/essentials/syntax)
describes the same thing from the front end's side.

## Named placeholders

```json
{ "hello": "Hola {name}" }
```

```python
translate(ctx, "hello", {"name": "Ana"})       # 'Hola Ana'
translate(ctx, "hello")                        # 'Hola ' - a missing value is empty, not an error
```

## Positional placeholders

```json
{ "route": "{0} to {1}" }
```

```python
translate(ctx, "route", ["Ljubljana", "Wien"])   # 'Ljubljana to Wien'
translate(ctx, "route", ["Ljubljana"])           # 'Ljubljana to ' - out of range is empty
```

## Plurals

Forms are separated by `|`, and the count picks one:

```json
{ "trips": "ni povezav | ena povezava | {count} povezav" }
```

```python
translate(ctx, "trips", 0)     # 'ni povezav'
translate(ctx, "trips", 1)     # 'ena povezava'
translate(ctx, "trips", 5)     # '5 povezav'
```

The count is available inside the message as both `{count}` and `{n}`.

**Which form a count selects is the subject of its own page**, and it is the one place where a
Slavic language needs your attention: see [plural rules](/guide/plurals).

## Linked messages

One message can pull in another:

```json
{
  "brand": "SŽ",
  "welcome": "Dobrodošli v @:brand"
}
```

```python
translate(ctx, "welcome")      # 'Dobrodošli v SŽ'
```

Linked keys follow the fallback chain, so `@:brand` resolves from the fallback locale if the current
one does not define it. A link that resolves to nothing renders as the key itself, which keeps the
gap visible.

### Modifiers

```json
{
  "welcome": "@.upper:brand",
  "polite":  "@.capitalize:greeting"
}
```

Three are built in — `upper`, `lower`, `capitalize` — and you can add your own:

```python
ctx = create_core_context(
    ...,
    modifiers={"reverse": lambda value, type_="text": value[::-1]},
)
```

A modifier takes the resolved string and the message type and returns a string.

::: tip capitalize and astral characters
`@.capitalize` uppercases the first *UTF-16 code unit*, not the first code point, because that is
what upstream's `charAt(0)` does. A message starting with an emoji or another astral character is
therefore left alone — in both languages, identically. This is the kind of detail a port either gets
right or quietly gets wrong.
:::

### Dynamic linked keys

```json
{ "dyn": "@:{ref}" }
```

```python
translate(ctx, "dyn", {"ref": "brand"})    # resolves whatever `ref` names
```

## Literals

A literal escapes the characters the syntax would otherwise claim:

```json
{
  "email": "{'@'} sign",
  "code":  "{'{'}braces{'}'}",
  "unicode": "{'\\u0041'}"
}
```

## Backslash escapes

In plain text, a backslash escapes `\{`, `\}`, `\@`, `\|` and `\\`.

## Nested and flat keys

Both work, and both resolve the same way they do in the browser:

```json
{
  "nested": { "deep": { "key": "value" } },
  "flat.dotted.key": "also value"
}
```

```python
translate(ctx, "nested.deep.key")     # 'value'
translate(ctx, "flat.dotted.key")     # 'also value'
```

The resolver walks the path first; if that finds nothing, the whole dotted string is tried as a
single key. That is upstream's order and it means a resource may mix the two styles.

## What interpolated values look like

A value that is not a string is rendered the way JavaScript would render it, not the way Python
would. `1.0` is `"1"`, `True` is `"true"`, `None` is the empty string, and a list or mapping becomes
indented JSON. Without this the same message would read differently on the two ends — `str(1.0)` is
`"1.0"` in Python and `String(1.0)` is `"1"` in JavaScript.

The one place they cannot agree: a Python `int` is exact at any size, while a JavaScript number is a
double. Past 2^53 the two print different digits, and this port prints the integer it was given
rather than throwing away precision the caller passed deliberately.
