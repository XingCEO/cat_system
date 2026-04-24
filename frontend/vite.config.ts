import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks(id) {
                    // React 核心
                    if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router-dom')) {
                        return 'vendor-react';
                    }
                    // 圖表庫
                    if (id.includes('node_modules/lightweight-charts')) {
                        return 'vendor-lwc';
                    }
                    if (id.includes('node_modules/recharts')) {
                        return 'vendor-recharts';
                    }
                    // Radix UI
                    if (id.includes('node_modules/@radix-ui')) {
                        return 'vendor-radix';
                    }
                    // 資料處理
                    if (id.includes('node_modules/@tanstack') || id.includes('node_modules/axios') || id.includes('node_modules/zustand')) {
                        return 'vendor-data';
                    }
                    // 工具庫
                    if (id.includes('node_modules/date-fns') || id.includes('node_modules/clsx') || id.includes('node_modules/tailwind-merge') || id.includes('node_modules/class-variance-authority') || id.includes('node_modules/lucide-react')) {
                        return 'vendor-utils';
                    }
                },
            },
        },
        chunkSizeWarningLimit: 600,
    },
})
