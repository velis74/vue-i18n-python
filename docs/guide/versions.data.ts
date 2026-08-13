import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Both numbers live in `vue_i18n/__init__.py` and nowhere else. The publish tool rewrites
// `__version__` there on every release, so a version written into a page by hand is stale the
// moment it is published - which is exactly what this loader exists to prevent. `VUE_I18N_VERSION`
// is rewritten by hand when the submodule pin moves; UPSTREAM.md lists that as a numbered step and
// `context_test.py` fails if it disagrees with UPSTREAM.md.
const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(HERE, '../../vue_i18n/__init__.py');

// The history table is the one thing on that page a loader cannot derive - which release tracked
// which upstream is a fact about the past, recorded when it happens. It lives in JSON rather than
// in the prose so the "no releases yet" wording cannot survive the first release: the page renders
// whichever branch the data says, and there is no sentence to forget to delete.
const RELEASES = resolve(HERE, 'releases.json');

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
  watch: [SOURCE, RELEASES],
  load() {
    return {
      package: read('__version__'),
      vueI18n: read('VUE_I18N_VERSION'),
      releases: JSON.parse(readFileSync(RELEASES, 'utf-8')) as Array<{
        version: string;
        tracks: string;
        note: string;
      }>,
    };
  },
};
