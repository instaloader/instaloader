import { NextRequest, NextResponse } from 'next/server'

interface MediaData {
  url: string
  index: number
  is_video: boolean
  video_url?: string
  thumbnail_url?: string
}

interface PostData {
  success: boolean
  shortcode: string
  owner: string
  caption: string
  media: MediaData[]
  is_carousel: boolean
  is_reel: boolean
  error?: string
}

// Try multiple methods to get Instagram data
async function getPostData(shortcode: string): Promise<PostData> {
  // Method 1: Try the graphql endpoint
  try {
    const data = await tryGraphQLMethod(shortcode)
    if (data && data.media.length > 0) return data
  } catch (e) {
    console.log('GraphQL method failed:', e)
  }

  // Method 2: Try embed page
  try {
    const data = await tryEmbedMethod(shortcode)
    if (data && data.media.length > 0) return data
  } catch (e) {
    console.log('Embed method failed:', e)
  }

  // Method 3: Try direct page scraping
  try {
    const data = await tryDirectMethod(shortcode)
    if (data && data.media.length > 0) return data
  } catch (e) {
    console.log('Direct method failed:', e)
  }

  throw new Error('No se pudo obtener el contenido. Verifica que el post sea público y la URL sea correcta.')
}

async function tryGraphQLMethod(shortcode: string): Promise<PostData | null> {
  const url = `https://www.instagram.com/graphql/query/?query_hash=b3055c01b4b222b8a47dc12b090e4e64&variables=${encodeURIComponent(JSON.stringify({ shortcode }))}`

  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json',
      'X-IG-App-ID': '936619743392459',
    },
  })

  if (!response.ok) return null

  const json = await response.json()
  const mediaData = json?.data?.shortcode_media

  if (!mediaData) return null

  return parseMediaData(mediaData, shortcode)
}

async function tryEmbedMethod(shortcode: string): Promise<PostData | null> {
  const embedUrl = `https://www.instagram.com/p/${shortcode}/embed/captioned/`

  const response = await fetch(embedUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Sec-Fetch-Mode': 'navigate',
    },
  })

  if (!response.ok) return null

  const html = await response.text()

  // Try to find JSON data in the page
  const jsonMatch = html.match(/window\.__additionalDataLoaded\s*\(\s*['"][^'"]+['"]\s*,\s*(\{.+?\})\s*\)\s*;/s)
  if (jsonMatch) {
    try {
      const data = JSON.parse(jsonMatch[1])
      const mediaData = data?.shortcode_media || data?.graphql?.shortcode_media
      if (mediaData) {
        return parseMediaData(mediaData, shortcode)
      }
    } catch {}
  }

  // Fallback: parse HTML directly
  return parseEmbedHtml(html, shortcode)
}

async function tryDirectMethod(shortcode: string): Promise<PostData | null> {
  // Try the main Instagram page with different approaches
  const urls = [
    `https://www.instagram.com/p/${shortcode}/?__a=1&__d=dis`,
    `https://www.instagram.com/reel/${shortcode}/?__a=1&__d=dis`,
  ]

  for (const url of urls) {
    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Instagram 219.0.0.12.117 Android',
          'Accept': '*/*',
        },
      })

      if (response.ok) {
        const json = await response.json()
        const mediaData = json?.items?.[0] || json?.graphql?.shortcode_media
        if (mediaData) {
          return parseMediaData(mediaData, shortcode)
        }
      }
    } catch {}
  }

  return null
}

function parseMediaData(data: any, shortcode: string): PostData {
  const media: MediaData[] = []

  const owner = data.owner?.username || data.user?.username || 'unknown'
  const caption = data.edge_media_to_caption?.edges?.[0]?.node?.text ||
                  data.caption?.text ||
                  data.caption ||
                  ''

  const isVideo = data.is_video || data.media_type === 2
  const isCarousel = data.__typename === 'GraphSidecar' ||
                     data.media_type === 8 ||
                     data.edge_sidecar_to_children?.edges?.length > 0 ||
                     data.carousel_media?.length > 0

  if (isCarousel) {
    // Handle carousel
    const edges = data.edge_sidecar_to_children?.edges || []
    const carouselMedia = data.carousel_media || []

    if (edges.length > 0) {
      edges.forEach((edge: any, idx: number) => {
        const node = edge.node
        media.push({
          url: node.display_url || node.display_resources?.pop()?.src,
          index: idx,
          is_video: node.is_video,
          video_url: node.video_url,
          thumbnail_url: node.display_url
        })
      })
    } else if (carouselMedia.length > 0) {
      carouselMedia.forEach((item: any, idx: number) => {
        const imageUrl = item.image_versions2?.candidates?.[0]?.url
        const videoUrl = item.video_versions?.[0]?.url
        media.push({
          url: videoUrl || imageUrl,
          index: idx,
          is_video: item.media_type === 2,
          video_url: videoUrl,
          thumbnail_url: imageUrl
        })
      })
    }
  } else {
    // Single media
    const imageUrl = data.display_url ||
                     data.image_versions2?.candidates?.[0]?.url ||
                     data.display_resources?.pop()?.src
    const videoUrl = data.video_url || data.video_versions?.[0]?.url

    media.push({
      url: isVideo ? (videoUrl || imageUrl) : imageUrl,
      index: 0,
      is_video: isVideo,
      video_url: videoUrl,
      thumbnail_url: imageUrl
    })
  }

  return {
    success: true,
    shortcode,
    owner,
    caption: typeof caption === 'string' ? caption : '',
    media,
    is_carousel: isCarousel,
    is_reel: data.product_type === 'clips' || data.product_type === 'reels'
  }
}

function parseEmbedHtml(html: string, shortcode: string): PostData | null {
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

  // Extract image URLs
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

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const shortcode = searchParams.get('shortcode')

  if (!shortcode) {
    return NextResponse.json(
      { success: false, error: 'Shortcode is required' },
      { status: 400 }
    )
  }

  if (!/^[A-Za-z0-9_-]+$/.test(shortcode)) {
    return NextResponse.json(
      { success: false, error: 'Invalid shortcode format' },
      { status: 400 }
    )
  }

  try {
    const postData = await getPostData(shortcode)
    return NextResponse.json(postData)

  } catch (error) {
    console.error('Error fetching post:', error)

    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error
          ? error.message
          : 'Error al obtener el post. Puede ser privado o no disponible.',
        shortcode,
        owner: '',
        caption: '',
        media: [],
        is_carousel: false,
        is_reel: false,
      },
      { status: 500 }
    )
  }
}
