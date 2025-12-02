'use client'

import { useState } from 'react'
import { Download, Instagram, Loader2, ImageIcon, AlertCircle, CheckCircle2 } from 'lucide-react'

interface ImageData {
  url: string
  index: number
  is_video: boolean
}

interface DownloadResponse {
  success: boolean
  shortcode: string
  owner: string
  caption: string
  images: ImageData[]
  is_carousel: boolean
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
      setError('Por favor ingresa una URL válida de Instagram (post o reel)')
      return
    }

    setLoading(true)

    try {
      const response = await fetch(`/api/download?shortcode=${shortcode}`)
      const data: DownloadResponse = await response.json()

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Error al obtener las imágenes')
      }

      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const downloadImage = async (imageUrl: string, index: number) => {
    setDownloadingIndex(index)
    try {
      const response = await fetch(imageUrl)
      const blob = await response.blob()
      const blobUrl = window.URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = blobUrl
      link.download = `instagram_${result?.shortcode}_${index + 1}.jpg`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)
    } catch (err) {
      console.error('Error downloading image:', err)
    } finally {
      setDownloadingIndex(null)
    }
  }

  const downloadAll = async () => {
    if (!result) return

    for (let i = 0; i < result.images.length; i++) {
      const img = result.images[i]
      if (!img.is_video) {
        await downloadImage(img.url, img.index)
        // Small delay between downloads
        await new Promise(resolve => setTimeout(resolve, 500))
      }
    }
  }

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      {/* Header */}
      <div className="text-center mb-12 fade-in">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-instagram-gradient mb-6 shadow-lg">
          <Instagram className="w-10 h-10 text-white" />
        </div>
        <h1 className="text-4xl md:text-5xl font-bold text-gray-800 dark:text-white mb-4">
          Instagram Carousel
          <span className="bg-clip-text text-transparent bg-instagram-gradient"> Downloader</span>
        </h1>
        <p className="text-gray-600 dark:text-gray-300 text-lg max-w-2xl mx-auto">
          Descarga todas las imágenes de cualquier carrusel de Instagram.
          Solo pega el enlace y obtén tus imágenes al instante.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="mb-10 fade-in">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.instagram.com/p/ABC123..."
              className="w-full px-6 py-4 text-lg rounded-2xl border-2 border-gray-200 dark:border-gray-700
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
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !url}
            className="btn-instagram px-8 py-4 rounded-2xl text-white font-semibold text-lg
                     flex items-center justify-center gap-3 min-w-[200px]"
          >
            {loading ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                Cargando...
              </>
            ) : (
              <>
                <Download className="w-6 h-6" />
                Obtener Imágenes
              </>
            )}
          </button>
        </div>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mb-8 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800
                      rounded-2xl flex items-center gap-3 text-red-600 dark:text-red-400 fade-in">
          <AlertCircle className="w-6 h-6 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="fade-in">
          {/* Post Info */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 mb-8 shadow-lg">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-2 text-green-600 dark:text-green-400 mb-2">
                  <CheckCircle2 className="w-5 h-5" />
                  <span className="font-medium">Post encontrado</span>
                </div>
                <p className="text-gray-600 dark:text-gray-300">
                  <span className="font-semibold">@{result.owner}</span>
                  {result.is_carousel && (
                    <span className="ml-2 text-sm bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 px-2 py-1 rounded-full">
                      Carrusel • {result.images.length} imágenes
                    </span>
                  )}
                </p>
                {result.caption && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm mt-2 line-clamp-2">
                    {result.caption.substring(0, 150)}
                    {result.caption.length > 150 && '...'}
                  </p>
                )}
              </div>
              {result.images.filter(img => !img.is_video).length > 1 && (
                <button
                  onClick={downloadAll}
                  className="px-6 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600
                           rounded-xl font-medium text-gray-700 dark:text-gray-200 transition-colors
                           flex items-center gap-2"
                >
                  <Download className="w-5 h-5" />
                  Descargar Todas
                </button>
              )}
            </div>
          </div>

          {/* Image Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 stagger-children">
            {result.images.map((image) => (
              <div
                key={image.index}
                className="image-card bg-white dark:bg-gray-800 rounded-2xl overflow-hidden shadow-lg"
              >
                <div className="aspect-square relative bg-gray-100 dark:bg-gray-700">
                  {image.is_video ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center text-gray-500 dark:text-gray-400">
                        <ImageIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">Video (no disponible)</p>
                      </div>
                    </div>
                  ) : (
                    <img
                      src={image.url}
                      alt={`Imagen ${image.index + 1}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  )}
                  <div className="absolute top-3 left-3 bg-black/60 text-white text-sm px-3 py-1 rounded-full">
                    {image.index + 1} / {result.images.length}
                  </div>
                </div>
                <div className="p-4">
                  <button
                    onClick={() => downloadImage(image.url, image.index)}
                    disabled={image.is_video || downloadingIndex === image.index}
                    className={`w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2
                              transition-colors ${
                                image.is_video
                                  ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                                  : 'bg-instagram-gradient text-white hover:opacity-90'
                              }`}
                  >
                    {downloadingIndex === image.index ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Download className="w-5 h-5" />
                    )}
                    {image.is_video ? 'No disponible' : 'Descargar'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="text-center mt-16 text-gray-500 dark:text-gray-400 text-sm">
        <p>
          Hecho con ❤️ usando{' '}
          <a
            href="https://github.com/instaloader/instaloader"
            target="_blank"
            rel="noopener noreferrer"
            className="text-pink-500 hover:text-pink-600 underline"
          >
            Instaloader
          </a>
        </p>
      </footer>
    </div>
  )
}
