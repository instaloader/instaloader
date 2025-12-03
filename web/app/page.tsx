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

// List of known GraphQL doc_ids (Instagram changes these every 2-4 weeks)
const GRAPHQL_DOC_IDS = [
  '10015901848480474',  // Current working (Dec 2025)
  '8845758582119845',   // Alternative
  '17991233890457762',  // Backup
]

// User agents for rotation
const USER_AGENTS = [
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Instagram 317.0.0.24.109 Android (33/13; 420dpi; 1080x2400; samsung; SM-G991B; o1s; exynos2100)',
]

// Client-side Instagram scraping functions
async function fetchViaProxy(url: string, userAgent?: string): Promise<string | null> {
  const proxies = [
    // Primary proxies (most reliable)
    `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
    `https://corsproxy.io/?${encodeURIComponent(url)}`,
    `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(url)}`,
    // Backup proxies
    `https://proxy.cors.sh/${url}`,
    `https://thingproxy.freeboard.io/fetch/${url}`,
    // Additional proxies
    `https://api.allorigins.win/get?url=${encodeURIComponent(url)}`,
    `https://corsproxy.org/?${encodeURIComponent(url)}`,
  ]

  const randomUA = userAgent || USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)]

  for (const proxyUrl of proxies) {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000)

      const response = await fetch(proxyUrl, {
        headers: {
          'Accept': 'text/html,application/xhtml+xml,application/json,*/*',
          'Accept-Language': 'en-US,en;q=0.9',
          'Cache-Control': 'no-cache',
          'User-Agent': randomUA,
        },
        signal: controller.signal
      })
      clearTimeout(timeoutId)

      if (response.ok) {
        let text = await response.text()

        // Handle allorigins.win/get response format (returns JSON with contents)
        if (proxyUrl.includes('allorigins.win/get')) {
          try {
            const json = JSON.parse(text)
            text = json.contents || text
          } catch {}
        }

        // Check if we got a valid Instagram response (not a login page or error)
        if (text && text.length > 500 && !text.includes('login') && !text.includes('Log in')) {
          console.log('[DEBUG] Proxy success:', proxyUrl.split('?')[0])
          return text
        }
      }
    } catch (e) {
      console.log('[DEBUG] Proxy failed:', proxyUrl.split('?')[0])
    }
  }
  return null
}

// Try to get carousel data from Instagram's GraphQL endpoint (the real method)
async function fetchGraphQLData(shortcode: string): Promise<any | null> {
  const graphqlUrl = 'https://www.instagram.com/api/graphql'
  const randomUA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)]

  // Try each doc_id until one works
  for (const docId of GRAPHQL_DOC_IDS) {
    console.log(`[DEBUG] Trying GraphQL with doc_id: ${docId}`)

    const formData = new URLSearchParams({
      av: '0',
      __d: 'www',
      __user: '0',
      __a: '1',
      __req: '3',
      __hs: '19624.HYP:instagram_web_pkg.2.1..0.0',
      dpr: '1',
      __ccg: 'UNKNOWN',
      __rev: '1008824440',
      __s: 'xf44ne:zhh75g:xr51e7',
      __hsi: '7282217488877343271',
      __dyn: '7xeUmwlEnwn8K2WnFw9-2i5U4e0yoW3q32360CEbo1nEhw2nVE4W0om78b87C0yE5ufz81s8hwGwQwoEcE7O2l0Fwqo31w9a9x-0z8-U2zxe2GewGwso88cobEaU2eUlwhEe87q7-0iK2S3qazo7u1xwIw8O321LwTwKG1pg661pwr86C1mwraCg',
      __csr: 'gZ3yFmJkillQvV6ybimnG8AmhqvADgjhClfSDfAHuWLzVo8ppcSoN4qKJKy3a4Cmy8m8nymcDAzo8y4EfwnA0y8x62p2m5AK0Z08nwjs1i0j80r9wDxu3awdo26w3wAw1GE0P83twg62wc8om1qwwobU2cgx05cE',
      __comet_req: '7',
      lsd: 'AVqbxe3J_YA',
      jazoest: '2957',
      __spin_r: '1008824440',
      __spin_b: 'trunk',
      __spin_t: '1695523385',
      fb_api_caller_class: 'RelayModern',
      fb_api_req_friendly_name: 'PolarisPostActionLoadPostQueryQuery',
      variables: JSON.stringify({
        shortcode: shortcode,
        fetch_comment_count: 40,
        parent_comment_count: 24,
        child_comment_count: 3,
        fetch_like_count: 10,
        fetch_tagged_user_count: null,
        fetch_preview_comment_count: 2,
        has_threaded_comments: true,
        hoisted_comment_id: null,
        hoisted_reply_id: null
      }),
      server_timestamps: 'true',
      doc_id: docId
    })

    // Try via proxy with each doc_id
    const proxies = [
      'https://corsproxy.io/?',
      'https://api.allorigins.win/raw?url=',
      'https://corsproxy.org/?',
    ]

    for (const proxyBase of proxies) {
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 15000)

        const response = await fetch(proxyBase + encodeURIComponent(graphqlUrl), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-IG-App-ID': '936619743392459',
            'X-FB-LSD': 'AVqbxe3J_YA',
            'X-ASBD-ID': '129477',
            'User-Agent': randomUA,
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
          },
          body: formData,
          signal: controller.signal
        })
        clearTimeout(timeoutId)

        if (response.ok) {
          const data = await response.json()
          const media = data?.data?.xdt_shortcode_media || data?.data?.shortcode_media
          if (media) {
            console.log(`[DEBUG] GraphQL success with doc_id: ${docId}`)
            return media
          }
        }
      } catch (e) {
        console.log(`[DEBUG] GraphQL proxy failed: ${proxyBase}`)
      }
    }
  }

  // Method 2: Fallback to ?__a=1&__d=dis endpoint (better for carousel data)
  console.log('[DEBUG] Trying ?__a=1&__d=dis endpoint')
  try {
    const jsonUrl = `https://www.instagram.com/p/${shortcode}/?__a=1&__d=dis`
    const html = await fetchViaProxy(jsonUrl, USER_AGENTS[3]) // Use Instagram app UA
    if (html) {
      try {
        const data = JSON.parse(html)
        const mediaData = data?.graphql?.shortcode_media || data?.items?.[0]
        if (mediaData) {
          console.log('[DEBUG] __a=1&__d=dis endpoint success')
          return mediaData
        }
      } catch {
        const jsonMatch = html.match(/"graphql"\s*:\s*(\{.+?"shortcode_media".+?\})\s*,\s*"showQRModal"/)
        if (jsonMatch) {
          try {
            const parsed = JSON.parse(jsonMatch[1])?.shortcode_media
            if (parsed) {
              console.log('[DEBUG] Extracted from HTML successfully')
              return parsed
            }
          } catch {}
        }
      }
    }
  } catch (e) {
    console.log('[DEBUG] JSON endpoint failed:', e)
  }

  // Method 3: Try reel endpoint
  console.log('[DEBUG] Trying reel endpoint')
  try {
    const reelUrl = `https://www.instagram.com/reel/${shortcode}/?__a=1&__d=dis`
    const html = await fetchViaProxy(reelUrl, USER_AGENTS[3])
    if (html) {
      try {
        const data = JSON.parse(html)
        const mediaData = data?.graphql?.shortcode_media || data?.items?.[0]
        if (mediaData) {
          console.log('[DEBUG] Reel endpoint success')
          return mediaData
        }
      } catch {}
    }
  } catch (e) {
    console.log('[DEBUG] Reel endpoint failed:', e)
  }

  return null
}

// Extract all images from Instagram page HTML
function extractAllImagesFromHtml(html: string): string[] {
  const images: string[] = []

  // Pattern 1: display_url in JSON
  const displayUrlMatches = html.matchAll(/"display_url"\s*:\s*"([^"]+)"/g)
  for (const match of displayUrlMatches) {
    const url = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    if (url.includes('cdninstagram') && !images.includes(url)) {
      images.push(url)
    }
  }

  // Pattern 2: src in sidecar edges
  const sidecarMatches = html.matchAll(/"node"\s*:\s*\{[^}]*"display_url"\s*:\s*"([^"]+)"/g)
  for (const match of sidecarMatches) {
    const url = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    if (url.includes('cdninstagram') && !images.includes(url)) {
      images.push(url)
    }
  }

  // Pattern 3: High-res images in display_resources
  const resourceMatches = html.matchAll(/"display_resources"\s*:\s*\[([^\]]+)\]/g)
  for (const match of resourceMatches) {
    const srcMatches = match[1].matchAll(/"src"\s*:\s*"([^"]+)"/g)
    let lastSrc = ''
    for (const srcMatch of srcMatches) {
      lastSrc = srcMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    }
    if (lastSrc && lastSrc.includes('cdninstagram') && !images.includes(lastSrc)) {
      images.push(lastSrc)
    }
  }

  // Pattern 4: carousel_media items (from ?__a=1&__d=dis response)
  const carouselMatches = html.matchAll(/"carousel_media"\s*:\s*\[([\s\S]*?)\]/g)
  for (const match of carouselMatches) {
    const urlMatches = match[1].matchAll(/"url"\s*:\s*"([^"]+)"/g)
    for (const urlMatch of urlMatches) {
      const url = urlMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
      if (url.includes('cdninstagram') && !images.includes(url)) {
        images.push(url)
      }
    }
  }

  // Pattern 5: image_versions2 candidates
  const candidateMatches = html.matchAll(/"candidates"\s*:\s*\[\s*\{\s*"width"\s*:\s*\d+[^}]*"url"\s*:\s*"([^"]+)"/g)
  for (const match of candidateMatches) {
    const url = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    if (url.includes('cdninstagram') && !images.includes(url)) {
      images.push(url)
    }
  }

  console.log(`[DEBUG] extractAllImagesFromHtml found ${images.length} images`)
  return images
}

// Try to extract carousel data from various JSON structures in HTML
function extractCarouselFromHtml(html: string): any | null {
  // Try to find edge_sidecar_to_children data
  const sidecarMatch = html.match(/"edge_sidecar_to_children"\s*:\s*(\{"edges"\s*:\s*\[[\s\S]*?\]\})/);
  if (sidecarMatch) {
    try {
      const sidecar = JSON.parse(sidecarMatch[1])
      if (sidecar?.edges?.length > 0) {
        console.log(`[DEBUG] Found sidecar with ${sidecar.edges.length} edges`)
        return { edge_sidecar_to_children: sidecar, __typename: 'GraphSidecar' }
      }
    } catch {}
  }

  // Try to find carousel_media array
  const carouselMatch = html.match(/"carousel_media"\s*:\s*(\[[\s\S]*?\])\s*[,}]/)
  if (carouselMatch) {
    try {
      const carousel = JSON.parse(carouselMatch[1])
      if (Array.isArray(carousel) && carousel.length > 0) {
        console.log(`[DEBUG] Found carousel_media with ${carousel.length} items`)
        return { carousel_media: carousel, product_type: 'carousel_container' }
      }
    } catch {}
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

  // Extract video URLs - collect all unique video URLs
  const videoUrls: string[] = []
  const videoMatches = html.matchAll(/"video_url":"([^"]+)"/g)
  for (const match of videoMatches) {
    const videoUrl = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    if (!videoUrls.includes(videoUrl)) {
      videoUrls.push(videoUrl)
    }
  }

  // If this is a video post, only add the video (not thumbnails as separate items)
  if (isVideo && videoUrls.length > 0) {
    const thumbMatch = html.match(/"display_url":"([^"]+)"/)
    const thumbUrl = thumbMatch ? thumbMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '') : undefined

    // Add only unique videos
    for (const videoUrl of videoUrls) {
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
  } else {
    // Not a video - extract image URLs from display_url
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
  }

  // Only try to find additional images if this is NOT a video post
  if (!isVideo || videoUrls.length === 0) {
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
  console.log('Starting data fetch for:', shortcode)

  // Method 1: Try the main Instagram page (has full carousel data)
  try {
    const mainUrl = `https://www.instagram.com/p/${shortcode}/`
    console.log('Trying main page:', mainUrl)
    const mainHtml = await fetchViaProxy(mainUrl)

    if (mainHtml) {
      // Try to extract shared_data JSON
      const sharedDataMatch = mainHtml.match(/window\._sharedData\s*=\s*(\{.+?\});\s*<\/script>/)
      if (sharedDataMatch) {
        try {
          const sharedData = JSON.parse(sharedDataMatch[1])
          const mediaData = sharedData?.entry_data?.PostPage?.[0]?.graphql?.shortcode_media
          if (mediaData) {
            console.log('Found data in _sharedData')
            const result = parseMediaDataClient(mediaData, shortcode)
            if (result.media.length > 0) return result
          }
        } catch (e) {
          console.log('sharedData parse error:', e)
        }
      }

      // Try additionalDataLoaded pattern
      const additionalMatch = mainHtml.match(/window\.__additionalDataLoaded\s*\(['"][^'"]+['"]\s*,\s*(\{.+?\})\s*\)/)
      if (additionalMatch) {
        try {
          const data = JSON.parse(additionalMatch[1])
          const mediaData = data?.graphql?.shortcode_media || data?.shortcode_media
          if (mediaData) {
            console.log('[DEBUG] Found data in __additionalDataLoaded')
            const result = parseMediaDataClient(mediaData, shortcode)
            if (result.media.length > 0) return result
          }
        } catch (e) {
          console.log('[DEBUG] additionalData parse error:', e)
        }
      }

      // Try to extract carousel data from HTML using new method
      const carouselData = extractCarouselFromHtml(mainHtml)
      if (carouselData) {
        console.log('[DEBUG] Found carousel data via extractCarouselFromHtml')
        const result = parseMediaDataClient(carouselData, shortcode)
        if (result.media.length > 1) return result
      }

      // Check if this is a video post first
      const isVideoPost = mainHtml.includes('"is_video":true') || mainHtml.includes('"video_url"')

      if (isVideoPost) {
        // Extract video URL
        const videoUrlMatch = mainHtml.match(/"video_url":"([^"]+)"/)
        if (videoUrlMatch) {
          const videoUrl = videoUrlMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
          const thumbMatch = mainHtml.match(/"display_url":"([^"]+)"/)
          const thumbUrl = thumbMatch ? thumbMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '') : undefined

          console.log('Found video via HTML extraction')
          return {
            success: true,
            shortcode,
            owner: 'instagram',
            caption: '',
            media: [{
              url: videoUrl,
              index: 0,
              is_video: true,
              video_url: videoUrl,
              thumbnail_url: thumbUrl
            }],
            is_carousel: false,
            is_reel: true
          }
        }
      }

      // Try extracting all images from HTML as fallback (only for non-video posts)
      const allImages = extractAllImagesFromHtml(mainHtml)
      if (allImages.length > 0) {
        console.log('Found', allImages.length, 'images via HTML extraction')
        // Filter out duplicates and small thumbnails
        const filtered = allImages.filter(url =>
          !url.includes('s150x150') &&
          !url.includes('s320x320') &&
          !url.includes('s240x240') &&
          !url.includes('s640x640')
        )
        const unique = [...new Set(filtered)]
        if (unique.length > 0) {
          return {
            success: true,
            shortcode,
            owner: 'instagram',
            caption: '',
            media: unique.map((url, idx) => ({
              url,
              index: idx,
              is_video: false
            })),
            is_carousel: unique.length > 1,
            is_reel: false
          }
        }
      }
    }
  } catch (e) {
    errors.push('main page failed')
    console.log('Main page method failed:', e)
  }

  // Method 2: Try embed page via CORS proxy
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

  // Method 3: Try reel embed URL
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

  // Method 4: Try GraphQL endpoint
  try {
    console.log('Trying GraphQL endpoint')
    const graphqlData = await fetchGraphQLData(shortcode)
    if (graphqlData) {
      const result = parseMediaDataClient(graphqlData, shortcode)
      if (result.media.length > 0) return result
    }
  } catch (e) {
    errors.push('graphql failed')
    console.log('GraphQL method failed:', e)
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

  // Check for carousel using multiple detection methods
  const isCarousel = data.__typename === 'GraphSidecar' ||
                     data.product_type === 'carousel_container' ||
                     data.media_type === 8 ||
                     (Array.isArray(data.edge_sidecar_to_children?.edges) && data.edge_sidecar_to_children.edges.length > 0) ||
                     (Array.isArray(data.carousel_media) && data.carousel_media.length > 0)

  console.log('Parsing data:', {
    typename: data.__typename,
    product_type: data.product_type,
    media_type: data.media_type,
    isCarousel,
    hasEdges: !!data.edge_sidecar_to_children?.edges?.length,
    hasCarouselMedia: !!data.carousel_media?.length
  })

  if (isCarousel) {
    const edges = Array.isArray(data.edge_sidecar_to_children?.edges) ? data.edge_sidecar_to_children.edges : []
    const carouselMedia = Array.isArray(data.carousel_media) ? data.carousel_media : []

    console.log('Carousel detected:', { edgesCount: edges.length, carouselMediaCount: carouselMedia.length })

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

        // Handle different API response structures
        const candidates = Array.isArray(item.image_versions2?.candidates) ? item.image_versions2.candidates : []
        const videoVersions = Array.isArray(item.video_versions) ? item.video_versions : []

        // Also check for display_url directly on the item
        const displayUrl = item.display_url
        const displayResources = Array.isArray(item.display_resources) ? item.display_resources : []
        const lastResource = displayResources.length > 0 ? displayResources[displayResources.length - 1] : null

        const imageUrl = displayUrl || (candidates.length > 0 ? candidates[0]?.url : undefined) || lastResource?.src
        const videoUrl = item.video_url || (videoVersions.length > 0 ? videoVersions[0]?.url : undefined)
        const url = videoUrl || imageUrl

        if (url) {
          media.push({
            url,
            index: idx,
            is_video: item.is_video === true || item.media_type === 2,
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

  console.log('Parsed media count:', media.length)

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
      const filename = `instagram_${result?.shortcode}_${mediaItem.index + 1}.${extension}`

      // For iOS/mobile: try to download via proxy, then open in new tab
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
      const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent)

      if (isIOS) {
        // On iOS, we need to use a workaround
        // First try to fetch via CORS proxy and create a blob URL
        try {
          const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(downloadUrl)}`
          const response = await fetch(proxyUrl)
          if (response.ok) {
            const blob = await response.blob()
            const blobUrl = window.URL.createObjectURL(blob)

            // Create a temporary link
            const link = document.createElement('a')
            link.href = blobUrl
            link.download = filename

            // For iOS Safari, we need to actually show the image in a new tab
            // and let the user long-press to save
            const newWindow = window.open('', '_blank')
            if (newWindow) {
              newWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <title>Guardar Imagen - ${filename}</title>
                  <style>
                    body { margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #000; color: #fff; text-align: center; }
                    img, video { max-width: 100%; height: auto; border-radius: 12px; }
                    .instructions { background: #1a1a1a; padding: 16px; border-radius: 12px; margin-bottom: 20px; }
                    .step { margin: 8px 0; }
                    .emoji { font-size: 1.5em; }
                  </style>
                </head>
                <body>
                  <div class="instructions">
                    <p class="step"><span class="emoji">👆</span> <strong>Mantén presionada la imagen</strong></p>
                    <p class="step"><span class="emoji">📥</span> <strong>Selecciona "Guardar imagen"</strong></p>
                  </div>
                  ${mediaItem.is_video
                    ? `<video src="${blobUrl}" controls playsinline style="width:100%"></video>`
                    : `<img src="${blobUrl}" alt="${filename}" />`
                  }
                </body>
                </html>
              `)
              newWindow.document.close()
            } else {
              // Popup blocked, open directly
              window.open(downloadUrl, '_blank')
            }
            return
          }
        } catch (proxyErr) {
          console.log('Proxy download failed, opening direct URL:', proxyErr)
        }

        // Fallback: open original URL
        window.open(downloadUrl, '_blank')

      } else if (isMobile) {
        // Android: try direct download first
        try {
          const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(downloadUrl)}`
          const response = await fetch(proxyUrl)
          if (response.ok) {
            const blob = await response.blob()
            const blobUrl = window.URL.createObjectURL(blob)

            const link = document.createElement('a')
            link.href = blobUrl
            link.download = filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            window.URL.revokeObjectURL(blobUrl)
            return
          }
        } catch {
          // Fallback to opening in new tab
        }
        window.open(downloadUrl, '_blank')

      } else {
        // Desktop: download directly via proxy
        try {
          const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(downloadUrl)}`
          const response = await fetch(proxyUrl)
          const blob = await response.blob()
          const blobUrl = window.URL.createObjectURL(blob)

          const link = document.createElement('a')
          link.href = blobUrl
          link.download = filename
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          window.URL.revokeObjectURL(blobUrl)
        } catch {
          // Fallback to direct URL
          const response = await fetch(downloadUrl)
          const blob = await response.blob()
          const blobUrl = window.URL.createObjectURL(blob)

          const link = document.createElement('a')
          link.href = blobUrl
          link.download = filename
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          window.URL.revokeObjectURL(blobUrl)
        }
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

  const [downloadingAll, setDownloadingAll] = useState(false)

  const downloadAll = async () => {
    if (!result) return

    const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent)

    if (isIOS) {
      // iOS: Open a single page with ALL images for easy saving
      setDownloadingAll(true)
      try {
        // First, fetch all images via proxy and create blob URLs
        const blobUrls: string[] = []
        for (const item of result.media) {
          try {
            const downloadUrl = item.is_video ? (item.video_url || item.url) : item.url
            const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(downloadUrl)}`
            const response = await fetch(proxyUrl)
            if (response.ok) {
              const blob = await response.blob()
              blobUrls.push(window.URL.createObjectURL(blob))
            } else {
              blobUrls.push(downloadUrl) // fallback to original URL
            }
          } catch {
            blobUrls.push(item.url) // fallback
          }
        }

        // Open a page with all images
        const newWindow = window.open('', '_blank')
        if (newWindow) {
          const imagesHtml = result.media.map((item, idx) => {
            const blobUrl = blobUrls[idx] || item.url
            return item.is_video
              ? `<div class="media-item">
                  <p class="counter">${idx + 1} de ${result.media.length}</p>
                  <video src="${blobUrl}" controls playsinline></video>
                </div>`
              : `<div class="media-item">
                  <p class="counter">${idx + 1} de ${result.media.length}</p>
                  <img src="${blobUrl}" alt="Imagen ${idx + 1}" />
                </div>`
          }).join('')

          newWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Guardar ${result.media.length} imágenes - @${result.owner}</title>
              <style>
                * { box-sizing: border-box; }
                body {
                  margin: 0;
                  padding: 16px;
                  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                  background: #000;
                  color: #fff;
                }
                .header {
                  text-align: center;
                  padding: 20px;
                  background: linear-gradient(135deg, #833AB4, #FD1D1D, #F77737);
                  border-radius: 16px;
                  margin-bottom: 20px;
                }
                .header h1 { margin: 0 0 8px 0; font-size: 1.2em; }
                .header p { margin: 0; opacity: 0.9; font-size: 0.9em; }
                .instructions {
                  background: #1a1a1a;
                  padding: 16px;
                  border-radius: 12px;
                  margin-bottom: 20px;
                  text-align: center;
                }
                .instructions p { margin: 8px 0; }
                .emoji { font-size: 1.3em; margin-right: 8px; }
                .media-item {
                  background: #1a1a1a;
                  border-radius: 12px;
                  margin-bottom: 16px;
                  overflow: hidden;
                }
                .media-item .counter {
                  padding: 12px;
                  margin: 0;
                  font-weight: bold;
                  border-bottom: 1px solid #333;
                }
                .media-item img, .media-item video {
                  width: 100%;
                  display: block;
                }
              </style>
            </head>
            <body>
              <div class="header">
                <h1>📸 ${result.media.length} archivos de @${result.owner}</h1>
                <p>Carrusel descargado</p>
              </div>
              <div class="instructions">
                <p><span class="emoji">👆</span><strong>Mantén presionada CADA imagen</strong></p>
                <p><span class="emoji">📥</span><strong>Selecciona "Guardar imagen"</strong></p>
              </div>
              ${imagesHtml}
            </body>
            </html>
          `)
          newWindow.document.close()
        }
      } finally {
        setDownloadingAll(false)
      }
    } else {
      // Desktop/Android: download one by one
      setDownloadingAll(true)
      for (const item of result.media) {
        await downloadMedia(item)
        await new Promise(resolve => setTimeout(resolve, 500))
      }
      setDownloadingAll(false)
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
                  disabled={downloadingAll}
                  className="px-4 md:px-6 py-2.5 md:py-3 bg-instagram-gradient hover:opacity-90
                           rounded-xl font-medium text-white transition-colors
                           flex items-center justify-center gap-2 w-full sm:w-auto disabled:opacity-70"
                >
                  {downloadingAll ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Preparando {result.media.length} archivos...
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5" />
                      Descargar Todo ({result.media.length})
                    </>
                  )}
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
              <span className="text-lg">📱</span>
              <span>
                <strong>iPhone/iPad:</strong> Se abrirá una ventana. Mantén presionada la imagen y selecciona "Guardar imagen" para guardarla en tu galería.
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
          v1.7.0
        </p>
      </footer>
    </div>
  )
}
