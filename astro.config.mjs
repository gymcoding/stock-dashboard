// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://techboost.dev',
  integrations: [
    mdx(),
    sitemap({
      // 개발 전용 Kitchen Sink는 prod 미생성이나 방어 심층으로 sitemap에서도 제외
      filter: (page) => !page.includes('/kitchen-sink'),
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
