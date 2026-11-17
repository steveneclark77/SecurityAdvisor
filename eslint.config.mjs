import js from '@eslint/js';
import globals from 'globals';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig([
  globalIgnores(['.venv/**', 'node_modules/**', 'staticfiles/**', 'media/**', 'private-evidence/**', 'test-artifacts/**', 'work/**']),
  {
    files: ['**/*.js'],
    extends: [js.configs.recommended],
    languageOptions: {
      sourceType: 'script',
      globals: globals.browser,
    },
  },
  {
    files: ['**/*.{mjs,cjs}'],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
]);
