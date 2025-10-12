# 🚀 Tag-Based File System - React Version

## ✨ Versión moderna con React 18 + Vite

Sistema de gestión de archivos basado en tags, construido con **React**, **Vite** y **FastAPI**.

---

## 🎯 Inicio Rápido

### 1. Instalar dependencias
```bash
yarn install
# o
npm install
```

### 2. Iniciar servidor de desarrollo
```bash
yarn dev
# o
npm run dev
```

Abre http://localhost:5173 en tu navegador.

---

## 📦 Estructura del Proyecto

```
src/
├── components/          # Componentes React
├── context/            # Context API (Theme, Notifications)
├── hooks/              # Custom Hooks
├── services/           # API calls
├── utils/              # Utilidades
├── App.jsx             # Componente principal
└── main.jsx            # Entry point
```

---

## ✨ Características

- ✅ Dark Mode persistente
- ✅ Drag & Drop para archivos
- ✅ Búsqueda y filtros
- ✅ Gestión de tags
- ✅ Notificaciones toast
- ✅ Responsive design

---

## 🔧 Scripts

```bash
yarn dev      # Desarrollo
yarn build    # Build producción
yarn preview  # Preview build
```

---

**Backend API:** Debe estar corriendo en `http://localhost:8000`

Ejecuta desde la raíz del proyecto:
```bash
python run_api.py
```

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
