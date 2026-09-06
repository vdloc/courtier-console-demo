import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // The GLB is Draco-compressed, so the decoder has to be reachable. It is
  // copied out of node_modules at build time rather than pulled from a CDN,
  // which keeps the viewer working offline and on an air-gapped client site.
  assetsInclude: ['**/*.glb', '**/*.hdr', '**/*.ktx2'],
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          react: ['react', 'react-dom'],
        },
      },
    },
  },
});
