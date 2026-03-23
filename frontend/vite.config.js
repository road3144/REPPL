import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), '');
    var apiTarget = env.VITE_API_TARGET || 'https://j14a401.p.ssafy.io';
    return {
        plugins: [react()],
        server: {
            proxy: {
                '/api': {
                    target: apiTarget,
                    changeOrigin: true,
                    secure: false,
                },
                '/ws': {
                    target: apiTarget,
                    changeOrigin: true,
                    secure: false,
                    ws: true,
                },
            },
        },
    };
});
