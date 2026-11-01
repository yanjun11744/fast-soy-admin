import { defineConfig } from '@soybeanjs/eslint-config-vue';

export default [
  { ignores: ['**/._*', 'dist/**', 'dist-ssr/**', 'coverage/**'] },
  ...(await defineConfig({
    'vue/component-name-in-template-casing': [
      'warn',
      'PascalCase',
      {
        registeredComponentsOnly: false,
        ignores: ['/^icon-/']
      }
    ]
  }))
];
