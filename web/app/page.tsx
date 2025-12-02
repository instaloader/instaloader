'use client'

import { useState } from 'react'
import { Download, Instagram, Loader2, ImageIcon, AlertCircle, CheckCircle2, Play, Film, Image } from 'lucide-react'

interface MediaData {
  url: string
  index: number
  is_video: boolean
  video_url?: string
  thumbnail_url?: string
}

interface DownloadResponse {
  success: boolean
  shortcode: string
  owner: string
  caption: string
  media: MediaData[]
  is_carousel: boolean
  is_reel: boolean
  error?: string
}

// Client-side Instagram scraping functions
async function fetchViaProxy(url: string): Promise<string | null> {
  const proxies = [
    `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
    `https://corsproxy.io/?${encodeURIComponent(url)}`,
    `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(url)}`,
  ]

  for (const proxyUrl of proxies) {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000)

      const response = await fetch(proxyUrl, {
        headers: { 'Accept': 'text/html,application/xhtml+xml,application/json' },
        signal: controller.signal
      })
      clearTimeout(timeoutId)

      if (response.ok) {
        const text = await response.text()
        if (text && text.length > 100) {
          return text
        }
      }
    } catch (e) {
      console.log('Proxy failed:', proxyUrl, e)
    }
  }
  return null
}

function parseEmbedHtmlClient(html: string, shortcode: string): DownloadResponse | null {
  const media: MediaData[] = []

  // Extract username
  const usernameMatch = html.match(/"username":"([^"]+)"/) ||
                        html.match(/@([a-zA-Z0-9._]+)/)
  const owner = usernameMatch ? usernameMatch[1] : 'unknown'

  // Extract caption
  const captionMatch = html.match(/"caption":"([^"]*)"/)
  let caption = captionMatch ? captionMatch[1] : ''
  caption = caption.replace(/\\u[\dA-F]{4}/gi, (match) =>
    String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16))
  ).replace(/\\n/g, '\n').replace(/\\"/g, '"')

  // Check for video
  const isVideo = html.includes('"is_video":true') || html.includes('video_url')
  const isReel = html.includes('"product_type":"clips"')

  // Extract video URLs
  const videoMatches = html.matchAll(/"video_url":"([^"]+)"/g)
  for (const match of videoMatches) {
    const videoUrl = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    const thumbMatch = html.match(/"display_url":"([^"]+)"/)
    const thumbUrl = thumbMatch ? thumbMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '') : undefined

    if (!media.find(m => m.video_url === videoUrl)) {
      media.push({
        url: videoUrl,
        index: media.length,
        is_video: true,
        video_url: videoUrl,
        thumbnail_url: thumbUrl
      })
    }
  }

  // Extract image URLs from display_url
  const displayMatches = html.matchAll(/"display_url":"([^"]+)"/g)
  for (const match of displayMatches) {
    const url = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    if (!media.find(m => m.url === url || m.thumbnail_url === url)) {
      media.push({
        url,
        index: media.length,
        is_video: false
      })
    }
  }

  // Try to find images in srcset
  const srcsetMatches = html.matchAll(/srcset="([^"]+)"/g)
  for (const match of srcsetMatches) {
    const srcset = match[1].replace(/&amp;/g, '&')
    const urls = srcset.split(',').map(s => s.trim().split(' ')[0])
    const highResUrl = urls[urls.length - 1]
    if (highResUrl?.includes('cdninstagram') && !media.find(m => m.url === highResUrl)) {
      media.push({
        url: highResUrl,
        index: media.length,
        is_video: false
      })
    }
  }

  // Also try to extract from EmbeddedMediaImage class
  const imgMatches = html.matchAll(/class="EmbeddedMediaImage"[^>]*src="([^"]+)"/g)
  for (const match of imgMatches) {
    const url = match[1].replace(/&amp;/g, '&')
    if (url.includes('cdninstagram') && !media.find(m => m.url === url)) {
      media.push({
        url,
        index: media.length,
        is_video: false
      })
    }
  }

  if (media.length === 0) return null

  // Filter out small thumbnails
  const filtered = media.filter(m =>
    !m.url.includes('s150x150') &&
    !m.url.includes('s320x320') &&
    !m.url.includes('s240x240')
  )

  return {
    success: true,
    shortcode,
    owner,
    caption,
    media: filtered.length > 0 ? filtered.map((m, i) => ({ ...m, index: i })) : media,
    is_carousel: filtered.length > 1,
    is_reel: isReel || isVideo
  }
}

async function getPostDataClient(shortcode: string): Promise<DownloadResponse> {
  const errors: string[] = []

  // Method 1: Try embed page via CORS proxy
  try {
    const embedUrl = `https://www.instagram.com/p/${shortcode}/embed/captioned/`
    console.log('Trying embed URL:', embedUrl)
    const html = await fetchViaProxy(embedUrl)

    if (html) {
      // Try to find JSON data in the page first
      const jsonMatch = html.match(/window\.__additionalDataLoaded\s*\(\s*['"][^'"]+['"]\s*,\s*(\{[\s\S]+?\})\s*\)\s*;/)
      if (jsonMatch) {
        try {
          const data = JSON.parse(jsonMatch[1])
          const mediaData = data?.shortcode_media || data?.graphql?.shortcode_media
          if (mediaData) {
            const result = parseMediaDataClient(mediaData, shortcode)
            if (result.media.length > 0) return result
          }
        } catch (e) {
          console.log('JSON parse error:', e)
        }
      }

      // Fallback: parse HTML directly
      const result = parseEmbedHtmlClient(html, shortcode)
      if (result && result.media.length > 0) {
        return result
      }
    }
  } catch (e) {
    errors.push('embed failed')
    console.log('Embed method failed:', e)
  }

  // Method 2: Try reel embed URL
  try {
    const reelUrl = `https://www.instagram.com/reel/${shortcode}/embed/captioned/`
    console.log('Trying reel URL:', reelUrl)
    const reelHtml = await fetchViaProxy(reelUrl)

    if (reelHtml) {
      const result = parseEmbedHtmlClient(reelHtml, shortcode)
      if (result && result.media.length > 0) {
        return result
      }
    }
  } catch (e) {
    errors.push('reel failed')
    console.log('Reel method failed:', e)
  }

  // Method 3: Try simple embed (non-captioned)
  try {
    const simpleUrl = `https://www.instagram.com/p/${shortcode}/embed/`
    console.log('Trying simple embed:', simpleUrl)
    const simpleHtml = await fetchViaProxy(simpleUrl)

    if (simpleHtml) {
      const result = parseEmbedHtmlClient(simpleHtml, shortcode)
      if (result && result.media.length > 0) {
        return result
      }
    }
  } catch (e) {
    errors.push('simple failed')
    console.log('Simple embed failed:', e)
  }

  throw new Error('No se pudo obtener el contenido. Verifica que el post sea público y la URL sea correcta.')
}

function parseMediaDataClient(data: any, shortcode: string): DownloadResponse {
  const media: MediaData[] = []

  if (!data) {
    return { success: false, shortcode, owner: 'unknown', caption: '', media: [], is_carousel: false, is_reel: false }
  }

  const owner = data.owner?.username || data.user?.username || 'unknown'

  // Safely extract caption
  let caption = ''
  try {
    caption = data.edge_media_to_caption?.edges?.[0]?.node?.text ||
              data.caption?.text ||
              (typeof data.caption === 'string' ? data.caption : '') ||
              ''
  } catch { caption = '' }

  const isVideo = data.is_video === true || data.media_type === 2
  const isCarousel = data.__typename === 'GraphSidecar' ||
                     data.media_type === 8 ||
                     (Array.isArray(data.edge_sidecar_to_children?.edges) && data.edge_sidecar_to_children.edges.length > 0) ||
                     (Array.isArray(data.carousel_media) && data.carousel_media.length > 0)

  if (isCarousel) {
    const edges = Array.isArray(data.edge_sidecar_to_children?.edges) ? data.edge_sidecar_to_children.edges : []
    const carouselMedia = Array.isArray(data.carousel_media) ? data.carousel_media : []

    if (edges.length > 0) {
      edges.forEach((edge: any, idx: number) => {
        const node = edge?.node
        if (!node) return

        const displayResources = Array.isArray(node.display_resources) ? node.display_resources : []
        const lastResource = displayResources.length > 0 ? displayResources[displayResources.length - 1] : null
        const url = node.display_url || lastResource?.src

        if (url) {
          media.push({
            url,
            index: idx,
            is_video: node.is_video === true,
            video_url: node.video_url || undefined,
            thumbnail_url: node.display_url || undefined
          })
        }
      })
    } else if (carouselMedia.length > 0) {
      carouselMedia.forEach((item: any, idx: number) => {
        if (!item) return

        const candidates = Array.isArray(item.image_versions2?.candidates) ? item.image_versions2.candidates : []
        const videoVersions = Array.isArray(item.video_versions) ? item.video_versions : []

        const imageUrl = candidates.length > 0 ? candidates[0]?.url : undefined
        const videoUrl = videoVersions.length > 0 ? videoVersions[0]?.url : undefined
        const url = videoUrl || imageUrl

        if (url) {
          media.push({
            url,
            index: idx,
            is_video: item.media_type === 2,
            video_url: videoUrl,
            thumbnail_url: imageUrl
          })
        }
      })
    }
  } else {
    // Single media
    const displayResources = Array.isArray(data.display_resources) ? data.display_resources : []
    const lastResource = displayResources.length > 0 ? displayResources[displayResources.length - 1] : null
    const candidates = Array.isArray(data.image_versions2?.candidates) ? data.image_versions2.candidates : []
    const videoVersions = Array.isArray(data.video_versions) ? data.video_versions : []

    const imageUrl = data.display_url ||
                     (candidates.length > 0 ? candidates[0]?.url : undefined) ||
                     lastResource?.src
    const videoUrl = data.video_url || (videoVersions.length > 0 ? videoVersions[0]?.url : undefined)

    const url = isVideo ? (videoUrl || imageUrl) : imageUrl

    if (url) {
      media.push({
        url,
        index: 0,
        is_video: isVideo,
        video_url: videoUrl,
        thumbnail_url: imageUrl
      })
    }
  }

  return {
    success: media.length > 0,
    shortcode,
    owner,
    caption: typeof caption === 'string' ? caption : '',
    media,
    is_carousel: isCarousel,
    is_reel: data.product_type === 'clips' || data.product_type === 'reels'
  }
}

export default function Home() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DownloadResponse | null>(null)
  const [downloadingIndex, setDownloadingIndex] = useState<number | null>(null)

  const extractShortcode = (inputUrl: string): string | null => {
    const patterns = [
      /instagram\.com\/p\/([A-Za-z0-9_-]+)/,
      /instagram\.com\/reel\/([A-Za-z0-9_-]+)/,
      /instagram\.com\/reels\/([A-Za-z0-9_-]+)/,
      /instagr\.am\/p\/([A-Za-z0-9_-]+)/,
    ]

    for (const pattern of patterns) {
      const match = inputUrl.match(pattern)
      if (match) return match[1]
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)

    const shortcode = extractShortcode(url)
    if (!shortcode) {
      setError('Por favor ingresa una URL válida de Instagram (post, carrusel o reel)')
      return
    }

    setLoading(true)

    try {
      // Try client-side scraping first (bypasses Vercel IP blocking)
      const data = await getPostDataClient(shortcode)
      setResult(data)
    } catch (clientErr) {
      console.log('Client-side failed, trying server:', clientErr)

      // Fallback to server-side API
      try {
        const response = await fetch(`/api/download?shortcode=${shortcode}`)
        const data: DownloadResponse = await response.json()

        if (!response.ok || !data.success) {
          throw new Error(data.error || 'Error al obtener el contenido')
        }

        setResult(data)
      } catch (serverErr) {
        setError(clientErr instanceof Error ? clientErr.message : 'Error al obtener el contenido. Verifica que el post sea público.')
      }
    } finally {
      setLoading(false)
    }
  }

  const downloadMedia = async (mediaItem: MediaData) => {
    setDownloadingIndex(mediaItem.index)
    try {
      const downloadUrl = mediaItem.is_video ? (mediaItem.video_url || mediaItem.url) : mediaItem.url
      const extension = mediaItem.is_video ? 'mp4' : 'jpg'

      // For iOS/mobile: open in new tab so user can long-press to save
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)

      if (isMobile) {
        // Open in new tab for mobile - user can long-press to save
        window.open(downloadUrl, '_blank')
      } else {
        // Desktop: download directly
        const response = await fetch(downloadUrl)
        const blob = await response.blob()
        const blobUrl = window.URL.createObjectURL(blob)

        const link = document.createElement('a')
        link.href = blobUrl
        link.download = `instagram_${result?.shortcode}_${mediaItem.index + 1}.${extension}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(blobUrl)
      }
    } catch (err) {
      console.error('Error downloading:', err)
      // Fallback: open in new tab
      const downloadUrl = mediaItem.is_video ? (mediaItem.video_url || mediaItem.url) : mediaItem.url
      window.open(downloadUrl, '_blank')
    } finally {
      setDownloadingIndex(null)
    }
  }

  const downloadAll = async () => {
    if (!result) return

    for (const item of result.media) {
      await downloadMedia(item)
      await new Promise(resolve => setTimeout(resolve, 800))
    }
  }

  const getPostTypeLabel = () => {
    if (!result) return ''
    if (result.is_reel) return 'Reel'
    if (result.is_carousel) return `Carrusel • ${result.media.length} archivos`
    if (result.media[0]?.is_video) return 'Video'
    return 'Imagen'
  }

  const getPostTypeIcon = () => {
    if (!result) return null
    if (result.is_reel || result.media[0]?.is_video) return <Film className="w-4 h-4" />
    if (result.is_carousel) return <ImageIcon className="w-4 h-4" />
    return <Image className="w-4 h-4" />
  }

  return (
    <div className="container mx-auto px-4 py-8 md:py-12 max-w-4xl">
      {/* Header */}
      <div className="text-center mb-10 fade-in">
        <div className="inline-flex items-center justify-center w-16 h-16 md:w-20 md:h-20 rounded-full bg-instagram-gradient mb-4 md:mb-6 shadow-lg">
          <Instagram className="w-8 h-8 md:w-10 md:h-10 text-white" />
        </div>
        <h1 className="text-3xl md:text-5xl font-bold text-gray-800 dark:text-white mb-3 md:mb-4">
          Instagram
          <span className="bg-clip-text text-transparent bg-instagram-gradient"> Downloader</span>
        </h1>
        <p className="text-gray-600 dark:text-gray-300 text-base md:text-lg max-w-2xl mx-auto px-4">
          Descarga fotos, carruseles y reels de Instagram.
          Pega el enlace y guarda el contenido en tu dispositivo.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="mb-8 fade-in">
        <div className="flex flex-col gap-3 md:flex-row md:gap-4">
          <div className="flex-1 relative">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.instagram.com/p/ABC123..."
              className="w-full px-4 md:px-6 py-3 md:py-4 text-base md:text-lg rounded-xl md:rounded-2xl border-2 border-gray-200 dark:border-gray-700
                       bg-white dark:bg-gray-800 text-gray-800 dark:text-white
                       focus:border-pink-500 focus:ring-4 focus:ring-pink-500/20
                       transition-all duration-300 outline-none
                       placeholder:text-gray-400"
              disabled={loading}
            />
            {url && (
              <button
                type="button"
                onClick={() => setUrl('')}
                className="absolute right-3 md:right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
              >
                ✕
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !url}
            className="btn-instagram px-6 md:px-8 py-3 md:py-4 rounded-xl md:rounded-2xl text-white font-semibold text-base md:text-lg
                     flex items-center justify-center gap-2 md:gap-3 md:min-w-[200px]"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 md:w-6 md:h-6 animate-spin" />
                <span>Cargando...</span>
              </>
            ) : (
              <>
                <Download className="w-5 h-5 md:w-6 md:h-6" />
                <span>Descargar</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800
                      rounded-xl flex items-start gap-3 text-red-600 dark:text-red-400 fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <p className="text-sm md:text-base">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="fade-in">
          {/* Post Info */}
          <div className="bg-white dark:bg-gray-800 rounded-xl md:rounded-2xl p-4 md:p-6 mb-6 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-green-600 dark:text-green-400 mb-2">
                  <CheckCircle2 className="w-5 h-5" />
                  <span className="font-medium">Contenido encontrado</span>
                </div>
                <p className="text-gray-600 dark:text-gray-300 flex flex-wrap items-center gap-2">
                  <span className="font-semibold">@{result.owner}</span>
                  <span className="text-sm bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 px-2 py-1 rounded-full flex items-center gap-1">
                    {getPostTypeIcon()}
                    {getPostTypeLabel()}
                  </span>
                </p>
                {result.caption && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm mt-2 line-clamp-2">
                    {result.caption.substring(0, 150)}
                    {result.caption.length > 150 && '...'}
                  </p>
                )}
              </div>
              {result.media.length > 1 && (
                <button
                  onClick={downloadAll}
                  className="px-4 md:px-6 py-2.5 md:py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600
                           rounded-xl font-medium text-gray-700 dark:text-gray-200 transition-colors
                           flex items-center justify-center gap-2 w-full sm:w-auto"
                >
                  <Download className="w-5 h-5" />
                  Descargar Todo
                </button>
              )}
            </div>
          </div>

          {/* Media Grid */}
          <div className={`grid gap-4 md:gap-6 stagger-children ${
            result.media.length === 1
              ? 'grid-cols-1 max-w-lg mx-auto'
              : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
          }`}>
            {result.media.map((item) => (
              <div
                key={item.index}
                className="image-card bg-white dark:bg-gray-800 rounded-xl md:rounded-2xl overflow-hidden shadow-lg"
              >
                <div className="aspect-square relative bg-gray-100 dark:bg-gray-700">
                  {item.is_video ? (
                    <>
                      {/* Video thumbnail or placeholder */}
                      {item.thumbnail_url ? (
                        <img
                          src={item.thumbnail_url}
                          alt={`Video ${item.index + 1}`}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full bg-gradient-to-br from-purple-500 to-pink-500" />
                      )}
                      {/* Play icon overlay */}
                      <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                        <div className="w-16 h-16 md:w-20 md:h-20 rounded-full bg-white/90 flex items-center justify-center">
                          <Play className="w-8 h-8 md:w-10 md:h-10 text-gray-800 ml-1" fill="currentColor" />
                        </div>
                      </div>
                      {/* Video badge */}
                      <div className="absolute top-3 right-3 bg-red-500 text-white text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1">
                        <Film className="w-3 h-3" />
                        VIDEO
                      </div>
                    </>
                  ) : (
                    <img
                      src={item.url}
                      alt={`Imagen ${item.index + 1}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  )}
                  {result.media.length > 1 && (
                    <div className="absolute top-3 left-3 bg-black/60 text-white text-sm px-3 py-1 rounded-full">
                      {item.index + 1} / {result.media.length}
                    </div>
                  )}
                </div>
                <div className="p-3 md:p-4">
                  <button
                    onClick={() => downloadMedia(item)}
                    disabled={downloadingIndex === item.index}
                    className="w-full py-2.5 md:py-3 rounded-xl font-medium flex items-center justify-center gap-2
                              transition-colors bg-instagram-gradient text-white hover:opacity-90 disabled:opacity-70"
                  >
                    {downloadingIndex === item.index ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Download className="w-5 h-5" />
                    )}
                    {item.is_video ? 'Descargar Video' : 'Descargar Imagen'}
                  </button>
                  <p className="text-xs text-center text-gray-500 dark:text-gray-400 mt-2">
                    {item.is_video ? 'MP4' : 'JPG'} • Máxima calidad
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Mobile tip */}
          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl text-blue-700 dark:text-blue-300 text-sm md:hidden">
            <p className="flex items-start gap-2">
              <span className="text-lg">💡</span>
              <span>
                <strong>Tip:</strong> Mantén presionada la imagen o video para guardarla en tu galería.
              </span>
            </p>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="text-center mt-12 md:mt-16 text-gray-500 dark:text-gray-400 text-sm">
        <p>
          Hecho con ❤️ para descargar contenido de Instagram
        </p>
        <p className="mt-2 text-xs">
          Solo funciona con posts públicos
        </p>
        <p className="mt-4 text-xs font-mono bg-gray-200 dark:bg-gray-700 inline-block px-2 py-1 rounded">
          v1.3.0
        </p>
      </footer>
    </div>
  )
}
