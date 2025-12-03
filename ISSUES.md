# Problemas del Instagram Downloader

## Estado Actual: v1.7.0

---

## Problemas Resueltos

### 1. Error de Vercel 404
- **Problema:** La app mostraba 404 en Vercel
- **Causa:** Root Directory no estaba configurado como `web`
- **Solución:** Configurar Root Directory = `web` en Vercel settings

### 2. Error de TypeScript con regex
- **Problema:** `error TS1501: This regular expression flag is only available when targeting 'es2018' or later`
- **Causa:** tsconfig.json tenía target `es2017`
- **Solución:** Cambiar target a `es2020` y reemplazar flag `/s` con `[\s\S]`

### 3. Videos mostrando miniaturas duplicadas
- **Problema:** Al descargar un video, aparecían 2 fotos iguales de la portada en lugar del video
- **Causa:** El código extraía tanto el video como las miniaturas como items separados
- **Solución:** Detectar si es video primero y solo agregar el video, no las miniaturas (v1.6.0)

### 4. Descarga en iPhone no funcionaba
- **Problema:** No se podían guardar las imágenes en iPhone
- **Causa:** Safari bloquea descargas directas
- **Solución:** Abrir nueva ventana con la imagen y mostrar instrucciones para "mantener presionado > guardar imagen"

---

## Mejoras Implementadas en v1.7.0

### 1. doc_id rotativos para GraphQL
- **Problema:** Instagram cambia el `doc_id` cada 2-4 semanas
- **Solución:** Implementar lista de doc_ids alternativos que se prueban en secuencia
- **doc_ids actuales:**
  - `10015901848480474` (Principal - Dic 2025)
  - `8845758582119845` (Alternativo)
  - `17991233890457762` (Respaldo)

### 2. User-Agent rotativo
- **Problema:** Instagram bloqueaba requests con el mismo User-Agent
- **Solución:** Implementar rotación entre 4 User-Agents diferentes (iPhone, Android, Desktop, Instagram App)

### 3. Más proxies CORS
- **Problema:** Algunos proxies estaban bloqueados
- **Solución:** Agregar más proxies alternativos:
  - `api.allorigins.win/raw` (principal)
  - `corsproxy.io` (principal)
  - `api.codetabs.com` (principal)
  - `proxy.cors.sh` (respaldo)
  - `thingproxy.freeboard.io` (respaldo)
  - `api.allorigins.win/get` (nuevo)
  - `corsproxy.org` (nuevo)

### 4. Mejor extracción de carruseles
- **Problema:** Carruseles mostraban solo 1-2 fotos
- **Solución:**
  - Nueva función `extractCarouselFromHtml()` para extraer datos de `edge_sidecar_to_children` y `carousel_media`
  - Múltiples patrones de regex para encontrar URLs de imágenes
  - Mejor manejo de respuestas del endpoint `?__a=1&__d=dis`

### 5. Logging de debug mejorado
- **Problema:** No había forma de debuggear qué método funcionaba
- **Solución:** Agregar logs `[DEBUG]` y `[SERVER DEBUG]` para cada paso del proceso
- **Uso:** Abrir consola del navegador (F12) para ver los logs

---

## Problemas Actuales (Pueden persistir)

### 1. Algunos carruseles siguen mostrando pocas fotos
- **Estado:** PARCIALMENTE RESUELTO
- **Causa:** Instagram limita datos en respuestas no autenticadas
- **Próximos pasos:**
  - Considerar implementar sesión con cookies
  - Usar API de terceros como respaldo (Apify, RapidAPI)

### 2. Algunos posts dan error "No se pudo obtener el contenido"
- **Estado:** MEJORADO pero puede ocurrir
- **Causa:**
  - IPs de Vercel están bloqueadas por Instagram
  - Posts privados o restringidos
- **Solución parcial:** El cliente ahora intenta múltiples métodos antes de fallar

### 3. No hay forma de testear en el entorno de desarrollo
- **Problema:** El sandbox de desarrollo no tiene acceso a Instagram
- **Error:** `getaddrinfo EAI_AGAIN www.instagram.com`
- **Workaround:** Probar directamente en producción (Vercel) usando los logs de debug

---

## Métodos de Scraping Implementados

### Cliente (page.tsx)
1. **Main page parsing** - `window._sharedData` y `__additionalDataLoaded`
2. **Carousel extraction** - `extractCarouselFromHtml()` para datos de carrusel
3. **HTML extraction** - Múltiples patrones regex para `display_url`
4. **Embed page** - `/p/{shortcode}/embed/captioned/`
5. **Reel embed** - `/reel/{shortcode}/embed/captioned/`
6. **GraphQL API** - POST con doc_ids rotativos
7. **Direct API** - `?__a=1&__d=dis` con Instagram App UA

### Servidor (route.ts)
1. **GraphQL con doc_ids rotativos** - Intenta múltiples doc_ids
2. **GraphQL con query_hash** - `query_hash=b3055c01b4b222b8a47dc12b090e4e64`
3. **Embed page scraping**
4. **Direct API** - `?__a=1&__d=dis`

---

## Herramientas de Referencia

Estas herramientas funcionan correctamente y se usaron como referencia:

1. **FastDL** - https://fastdl.app/carousel
2. **IQSaved** - https://iqsaved.com/carousel/
3. **SSSInstagram** - https://sssinstagram.com/

### Repositorio de referencia
- **instagram-media-scraper** - https://github.com/ahmedrangel/instagram-media-scraper
  - Usa GraphQL con `doc_id` rotativo
  - Detecta carruseles con `product_type === 'carousel_container'`
  - Extrae media de `carousel_media` array

---

## Cómo Debuggear

1. Abre la consola del navegador (F12)
2. Ingresa una URL de Instagram
3. Observa los logs `[DEBUG]` que muestran:
   - Qué proxy se está usando
   - Qué doc_id funcionó
   - Cuántas imágenes se encontraron
   - Qué método tuvo éxito

---

## Historial de Versiones

| Versión | Cambios |
|---------|---------|
| v1.5.0 | GraphQL API + Download All para iOS |
| v1.6.0 | Fix video duplicado - muestra video en lugar de miniaturas |
| v1.6.1 | Más proxies CORS + mejor detección de login |
| v1.6.2 | Fix detección carousel con `product_type: carousel_container` |
| v1.7.0 | doc_ids rotativos + User-Agent rotativo + más proxies + mejor extracción carrusel + logging debug |

---

*Última actualización: 2025-12-03*
