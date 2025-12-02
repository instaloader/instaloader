# Instagram Carousel Downloader - Web App

Una aplicación web moderna para descargar imágenes de carruseles de Instagram.

## Características

- Interfaz moderna y responsive
- Descarga de imágenes individuales o todas a la vez
- Soporte para posts y reels
- Previsualización de imágenes antes de descargar
- Diseño con gradiente de Instagram

## Despliegue en Vercel

### Opción 1: Un click deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/tu-usuario/instaloader/tree/main/web)

### Opción 2: Manual

1. Instala Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Navega al directorio web:
   ```bash
   cd web
   ```

3. Despliega:
   ```bash
   vercel
   ```

4. Para producción:
   ```bash
   vercel --prod
   ```

## Desarrollo Local

1. Instala las dependencias:
   ```bash
   npm install
   ```

2. Ejecuta el servidor de desarrollo:
   ```bash
   npm run dev
   ```

3. Abre [http://localhost:3000](http://localhost:3000)

## Estructura del Proyecto

```
web/
├── app/
│   ├── api/
│   │   └── download/
│   │       └── route.ts      # API endpoint
│   ├── globals.css           # Estilos globales
│   ├── layout.tsx            # Layout principal
│   └── page.tsx              # Página principal
├── public/                   # Assets estáticos
├── package.json
├── vercel.json               # Configuración de Vercel
├── tailwind.config.ts
└── next.config.js
```

## API

### GET /api/download

Obtiene las imágenes de un post de Instagram.

**Parámetros:**
- `shortcode`: El código corto del post (ej: ABC123)

**Respuesta:**
```json
{
  "success": true,
  "shortcode": "ABC123",
  "owner": "username",
  "caption": "Post caption...",
  "images": [
    {
      "url": "https://...",
      "index": 0,
      "is_video": false
    }
  ],
  "is_carousel": true
}
```

## Limitaciones

- Solo funciona con posts públicos
- Los posts privados requieren autenticación adicional
- Instagram puede bloquear solicitudes excesivas (rate limiting)

## Tecnologías

- [Next.js 14](https://nextjs.org/) - Framework React
- [Tailwind CSS](https://tailwindcss.com/) - Estilos
- [Lucide React](https://lucide.dev/) - Iconos
- [Vercel](https://vercel.com/) - Hosting

## Notas

Este proyecto es solo para uso personal y educativo. Respeta los términos de servicio de Instagram y los derechos de autor de los creadores de contenido.
