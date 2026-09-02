import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { AdminApp } from "@/components/admin/admin-app.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"

// Khong dung router: server tra index.html cho moi duong dan (xem webserver._spa) nen chi
// can doc pathname mot lan. Ca app chi co dung 2 trang.
const isAdmin = window.location.pathname.replace(/\/+$/, "") === "/admin"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>{isAdmin ? <AdminApp /> : <App />}</ThemeProvider>
  </StrictMode>
)
