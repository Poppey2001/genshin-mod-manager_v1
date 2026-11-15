import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  root: "ui",
  plugins: [svelte()],
  clearScreen: false,
  resolve: {
    alias: {
      // Gemeinsame Übersetzungen und Icons der Python-Version (eine Quelle).
      "@locales": `${repoRoot}app/i18n/locales`,
      "@assets": `${repoRoot}assets`,
    },
  },
  server: {
    port: 1420,
    strictPort: true,
    fs: { allow: [repoRoot] },
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    target: "es2022",
  },
});
