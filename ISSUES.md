# Problemas del Instagram Downloader

## Estado Actual: v1.6.2

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

## Problemas Actuales (Sin Resolver)

### 1. Carruseles muestran solo 1-2 fotos en lugar de todas
- **Problema:** Un carrusel de 6 fotos solo muestra 1 o 2
- **URLs de prueba que fallan:**
  - `https://www.instagram.com/p/DRNBNPlDsSc/`
- **Intentos de solución:**
  - Agregado `product_type === 'carousel_container'` para detección
  - Agregados múltiples proxies CORS
  - Implementado GraphQL API con `doc_id: 10015901848480474`
  - Mejorado parsing de `edge_sidecar_to_children` y `carousel_media`
- **Estado:** NO FUNCIONA - Necesita más investigación

### 2. Algunos posts dan error "No se pudo obtener el contenido"
- **Problema:** Posts públicos dan error de que no se puede obtener
- **Causa probable:**
  - Instagram bloquea las IPs de Vercel
  - Los proxies CORS están siendo bloqueados
  - Los parámetros del GraphQL API pueden estar desactualizados
- **Estado:** NO FUNCIONA

### 3. No hay forma de testear en el entorno de desarrollo
- **Problema:** El sandbox de desarrollo no tiene acceso a Instagram
- **Error:** `getaddrinfo EAI_AGAIN www.instagram.com`
- **Impacto:** No se puede debuggear ni probar cambios antes de deploy

---

## Métodos de Scraping Implementados

### Cliente (page.tsx)
1. **Main page parsing** - `window._sharedData` y `__additionalDataLoaded`
2. **HTML extraction** - Buscar `display_url` en el HTML
3. **Embed page** - `/p/{shortcode}/embed/captioned/`
4. **Reel embed** - `/reel/{shortcode}/embed/captioned/`
5. **GraphQL API** - POST a `/api/graphql` con `doc_id`

### Servidor (route.ts)
1. **GraphQL con doc_id** - `doc_id: 10015901848480474`
2. **GraphQL con query_hash** - `query_hash=b3055c01b4b222b8a47dc12b090e4e64`
3. **Embed page scraping**
4. **Direct API** - `?__a=1&__d=dis`

### Proxies CORS usados
- `api.allorigins.win`
- `corsproxy.io`
- `api.codetabs.com`
- `proxy.cors.sh`
- `thingproxy.freeboard.io`

---

## Herramientas de Referencia que SÍ Funcionan

Estas herramientas funcionan correctamente y podrían usarse como referencia:

1. **FastDL** - https://fastdl.app/carousel
2. **IQSaved** - https://iqsaved.com/carousel/
3. **The Social Cat** - https://thesocialcat.com/tools/instagram-photo-downloader
4. **SSSInstagram** - https://sssinstagram.com/

### Repositorio de referencia
- **instagram-media-scraper** - https://github.com/ahmedrangel/instagram-media-scraper
  - Usa GraphQL con `doc_id: 10015901848480474`
  - Detecta carruseles con `product_type === 'carousel_container'`
  - Extrae media de `carousel_media` array

---

## Próximos Pasos Sugeridos

1. [ ] Analizar el código exacto de `instagram-media-scraper` y replicarlo
2. [ ] Probar con un servidor proxy propio en lugar de proxies públicos
3. [ ] Considerar usar una API de terceros (Apify, RapidAPI)
4. [ ] Agregar mejor logging para diagnosticar qué datos devuelve Instagram
5. [ ] Probar desde la consola del navegador (F12) para ver los logs de debug

---

## Historial de Versiones

| Versión | Cambios |
|---------|---------|
| v1.5.0 | GraphQL API + Download All para iOS |
| v1.6.0 | Fix video duplicado - muestra video en lugar de miniaturas |
| v1.6.1 | Más proxies CORS + mejor detección de login |
| v1.6.2 | Fix detección carousel con `product_type: carousel_container` |

---

*Última actualización: 2025-12-03*
