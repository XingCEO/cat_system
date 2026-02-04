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
        host: true,
        allowedHosts: true, // 允許所有 Host header，解決 ngrok 報錯
        port: 5174,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
            '/realtime': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    // React 核心
                    'vendor-react': ['react', 'react-dom', 'react-router-dom'],
                    // 圖表庫
                    'vendor-charts': ['recharts', 'lightweight-charts'],
                    // UI 元件
                    'vendor-radix': [
                        '@radix-ui/react-alert-dialog',
                        '@radix-ui/react-checkbox',
                        '@radix-ui/react-dialog',
                        '@radix-ui/react-dropdown-menu',
                        '@radix-ui/react-label',
                        '@radix-ui/react-popover',
                        '@radix-ui/react-select',
                        '@radix-ui/react-slider',
                        '@radix-ui/react-slot',
                        '@radix-ui/react-switch',
                        '@radix-ui/react-tabs',
                        '@radix-ui/react-toast',
                        '@radix-ui/react-tooltip',
                    ],
                    // 資料處理
                    'vendor-data': ['@tanstack/react-query', '@tanstack/react-table', 'axios', 'zustand'],
                    // 工具庫
                    'vendor-utils': ['date-fns', 'clsx', 'tailwind-merge', 'class-variance-authority', 'lucide-react'],
                },
            },
        },
        chunkSizeWarningLimit: 600,
    },
})
