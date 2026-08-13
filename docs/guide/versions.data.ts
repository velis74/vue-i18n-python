import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Both numbers live in `vue_i18n/__init__.py` and nowhere else. The publish tool rewrites
// `__version__` there on every release, so a version written into a page by hand is stale the
// moment it is published - which is exactly what this loader exists to prevent. `VUE_I18N_VERSION`
// is rewritten by hand when the submodule pin moves; UPSTREAM.md lists that as a numbered step and
// `context_test.py` fails if it disagrees with UPSTREAM.md.
const SOURCE = resolve(dirname(fileURLToPath(import.meta.url)), '../../vue_i18n/__init__.py');

function read(name: string): string {
  const source = readFileSync(SOURCE, 'utf-8');
  // Anchored to the start of a line so a mention inside a docstring or comment cannot match.
  const match = source.match(new RegExp(`^${name}\\s*=\\s*["']([^"']+)["']`, 'm'));
  if (!match) {
    throw new Error(`${name} not found in ${SOURCE} - the docs cannot state a version they cannot read`);
  }
  return match[1];
}

export default {
  watch: [SOURCE],
  load() {
    return { package: read('__version__'), vueI18n: read('VUE_I18N_VERSION') };
  },
};
