#!/bin/sh
# Bundle the upstream TypeScript that the corpus generators run against.
#
# The generators must execute vue-i18n's *own* code, not a transcription of it, so the bundle is
# built straight from a clone of the upstream repository. Two things make that work without
# installing the monorepo: upstream's sources import each other as `@intlify/*`, which esbuild
# resolves through the clone's own tsconfig `paths`, and `const enum` (which Node's built-in type
# stripping refuses) is inlined by esbuild.
#
# `__DEV__` is a compile-time flag in upstream's build. It is defined as true here because that is
# the setting under which the compiler reports error messages, and the messages are part of what
# the compile corpus pins.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/upstream-bundle"

# The submodule at vendor/vue-i18n is the source of truth: it is pinned to the released version this
# port tracks, so "which upstream" is answered by git rather than by whatever clone happens to be on
# the machine. An explicit path still overrides it, which is how you would try a candidate release
# without moving the pin.
DEFAULT_UPSTREAM="$HERE/../../vendor/vue-i18n"

if [ $# -lt 1 ]; then
  if [ ! -f "$DEFAULT_UPSTREAM/package.json" ]; then
    echo "error: $DEFAULT_UPSTREAM is empty - run: git submodule update --init" >&2
    exit 2
  fi
  set -- "$DEFAULT_UPSTREAM"
fi

UPSTREAM=$(cd "$1" && pwd)
VERSION=$(node -p "require('$UPSTREAM/package.json').version")
echo "upstream: intlify/vue-i18n@$VERSION at $UPSTREAM"

mkdir -p "$OUT"
printf "%s\n" "$VERSION" > "$OUT/version.txt"

# esbuild reads the tsconfig nearest to each file it touches. Without this one it would find the
# repository's, which extends a config that only exists after an npm install; an empty config here
# keeps the entry points out of that. Upstream's own tsconfig still governs upstream's sources,
# which is what supplies the `@intlify/*` paths.
printf "{}\n" > "$OUT/tsconfig.json"

# The entry points name the upstream files this project ports, and nothing else: whatever the
# generators can reach is exactly what the corpora can pin.
cat > "$OUT/entry_compile.mjs" <<EOF
export { createParser } from '$UPSTREAM/packages/message-compiler/src/parser.ts';
export { createTokenizer, TokenTypes } from '$UPSTREAM/packages/message-compiler/src/tokenizer.ts';
EOF

cat > "$OUT/entry_resolve.mjs" <<EOF
export {
  parse,
  resolveValue,
  resolveWithKeyValue
} from '$UPSTREAM/packages/core-base/src/resolver.ts';
EOF

cat > "$OUT/entry_fallback.mjs" <<EOF
export {
  fallbackWithSimple,
  fallbackWithLocaleChain
} from '$UPSTREAM/packages/core-base/src/fallbacker.ts';
EOF

for name in compile resolve fallback; do
  # No --tsconfig here on purpose: that flag applies one config to every file and would take
  # upstream's own `paths` out of play, at which point `@intlify/shared` resolves to whatever
  # version happens to be installed in some node_modules up the tree. The check below is what
  # notices if that ever starts happening anyway.
  # `__DEV__` and `__VERSION__` are compile-time defines in upstream's own build. `__DEV__` is true
  # because that is the setting under which the compiler reports error messages, and the messages
  # are part of what the compile corpus pins. `__VERSION__` only has to exist - core-base reads it
  # into a constant at module scope, so without it the bundle throws on import.
  npx --yes esbuild@0.28.2 --bundle --format=esm \
    --define:__DEV__=true --define:__VERSION__="\"$VERSION\"" \
    --outfile="$OUT/upstream_$name.mjs" "$OUT/entry_$name.mjs"
  if grep -q "node_modules/@intlify" "$OUT/upstream_$name.mjs"; then
    echo "error: $name bundle pulled in an installed @intlify package instead of the clone" >&2
    exit 1
  fi
done
