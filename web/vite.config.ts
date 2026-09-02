import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { VitePWA } from "vite-plugin-pwa"

// Cong mac dinh cua WEB_PORT trong .env; `npm run dev` proxy API sang bot dang chay.
const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:10240"

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["apple-touch-icon.png"],
      manifest: {
        name: "Ghi bài — bàn 3 cây",
        short_name: "Ghi bài",
        description: "Xem bàn 3 cây đang chơi: bảng xếp hạng và chi tiết từng ván.",
        lang: "vi",
        // Khong kem ?k= duoc vi manifest dung chung cho moi nhom; app tu doc token
        // da luu trong localStorage khi mo lai. Xem src/lib/token.ts.
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#0e3b2d",
        theme_color: "#0e3b2d",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        // API, webhook va trang moi /i/<ma> phai di thang ra mang, khong duoc tra ve
        // index.html - trang moi la HTML server-side, khong phai route cua SPA.
        navigateFallbackDenylist: [/^\/api\//, /^\/zalo\//, /^\/healthz$/, /^\/i\//],
        runtimeCaching: [
          {
            // Mat song van xem duoc ban vua tai; co song thi luon uu tien du lieu moi.
            urlPattern: ({ url }) => url.pathname === "/api/board",
            handler: "NetworkFirst",
            options: {
              cacheName: "ghibai-board",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 8, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
})
