import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(rootDir, "src/background.ts"),
        content: resolve(rootDir, "src/content.ts"),
        sidepanel: resolve(rootDir, "src/sidepanel/index.html"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
