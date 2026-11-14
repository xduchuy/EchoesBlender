import { defineConfig } from "vite";

export default defineConfig({
  assetsInclude: ["**/*.glb", "**/*.wasm"],
  build: {
    outDir: "dist",
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 750,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three"],
        },
      },
    },
  },
});
