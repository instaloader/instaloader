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
      const response = await fetch(`/api/download?shortcode=${shortcode}`)
      const data: DownloadResponse = await response.json()

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Error al obtener el contenido')
      }

      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
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
      </footer>
    </div>
  )
}
