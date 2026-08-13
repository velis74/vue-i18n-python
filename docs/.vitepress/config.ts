import { defineConfig } from 'vitepress';

export default defineConfig({
  title: 'vue-i18n-python',
  description: 'An unofficial Python port of vue-i18n: same message files, same API, same behaviour',
  ignoreDeadLinks: [/^http:\/\/localhost/],
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/guide/rationale' },
      { text: 'API Reference', link: '/api/' },
    ],
    // Reading order, not alphabetical. The guide opens with why the library exists and a start that
    // works on its own; then the two subjects a reader actually has questions about, the message
    // format and plurals; then the two that decide whether they can trust it, differences and how
    // upstream is tracked.
    sidebar: {
      '/guide/': [
        {
          text: 'Introduction',
          items: [
            { text: 'Why this exists', link: '/guide/rationale' },
            { text: 'Getting started', link: '/guide/getting-started' },
          ],
        },
        {
          text: 'Using it',
          items: [
            { text: 'Message format', link: '/guide/message-format' },
            { text: 'Plural rules', link: '/guide/plurals' },
            { text: 'Fallback locales', link: '/guide/fallback' },
          ],
        },
        {
          text: 'Trusting it',
          items: [
            { text: 'Differences from vue-i18n', link: '/guide/differences' },
            { text: 'Following upstream', link: '/guide/versioning' },
            { text: 'Which version tracks which', link: '/guide/version-translation' },
            { text: 'How it is verified', link: '/guide/conformance' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/api/' },
            { text: 'create_core_context', link: '/api/context' },
            { text: 'translate', link: '/api/translate' },
            { text: 'datetime and number', link: '/api/datetime-number' },
            { text: 'plurals', link: '/api/plurals' },
          ],
        },
      ],
    },
    socialLinks: [{ icon: 'github', link: 'https://github.com/velis74/vue-i18n-python' }],
    footer: {
      message:
        'Released under the MIT License. vue-i18n is © kazuya kawaguchi and contributors; ' +
        'this is an unofficial port and is not affiliated with intlify.',
      copyright: 'Copyright © 2026 Jure Erznožnik',
    },
    search: { provider: 'local' },
  },
});
