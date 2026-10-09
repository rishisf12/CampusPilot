import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        {
          allowConstantExport: true,
          // Hooks, icon/label tables and formatting helpers are exported beside
          // the components that use them; splitting each into its own file would
          // only add indirection without changing what can hot-reload.
          allowExportNames: [
            'useAuth',
            'readPendingEmail',
            'useProfile',
            'SECTION_ICONS',
            'SECTION_LABELS',
            'num',
            'money',
            'pctChange',
          ],
        },
      ],
      // An empty catch is an explicit "ignore this failure" in places like
      // best-effort cache reads - it is not accidental dead code.
      'no-empty': ['error', { allowEmptyCatch: true }],
      // A leading underscore marks a deliberately unused binding (rest-sibling
      // omission, a signature-matching stub); that intent should be enough.
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          destructuredArrayIgnorePattern: '^_',
          ignoreRestSiblings: true,
        },
      ],
    },
  },
  {
    linterOptions: {
      // Surfaced through --max-warnings 0 so a stale directive fails CI.
      reportUnusedDisableDirectives: 'warn',
    },
  }
);
