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
  const graphqlUrl = 'https://www.instagram.com/api/graphql'
  const randomUA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)]

  // Try each doc_id until one works
  for (const docId of GRAPHQL_DOC_IDS) {
    console.log(`[SERVER DEBUG] Trying GraphQL with doc_id: ${docId}`)

    try {
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

      const response = await fetch(graphqlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-IG-App-ID': '936619743392459',
          'X-FB-LSD': 'AVqbxe3J_YA',
          'X-ASBD-ID': '129477',
          'User-Agent': randomUA,
          'Origin': 'https://www.instagram.com',
          'Referer': 'https://www.instagram.com/',
          'Sec-Fetch-Site': 'same-origin',
          'Sec-Fetch-Mode': 'cors',
        },
        body: formData.toString()
      })

      if (response.ok) {
        const json = await response.json()
        const mediaData = json?.data?.xdt_shortcode_media || json?.data?.shortcode_media
        if (mediaData) {
          console.log(`[SERVER DEBUG] GraphQL success with doc_id: ${docId}`)
          return parseMediaData(mediaData, shortcode)
        }
      }
    } catch (e) {
      console.log(`[SERVER DEBUG] GraphQL doc_id ${docId} failed:`, e)
    }
  }

  // Method 2: Fallback to old query_hash method
  console.log('[SERVER DEBUG] Trying query_hash method')
  try {
    const url = `https://www.instagram.com/graphql/query/?query_hash=b3055c01b4b222b8a47dc12b090e4e64&variables=${encodeURIComponent(JSON.stringify({ shortcode }))}`

    const response = await fetch(url, {
      headers: {
        'User-Agent': randomUA,
        'Accept': 'application/json',
        'X-IG-App-ID': '936619743392459',
        'Sec-Fetch-Site': 'same-origin',
      },
    })

    if (response.ok) {
      const json = await response.json()
      const mediaData = json?.data?.shortcode_media
      if (mediaData) {
        console.log('[SERVER DEBUG] query_hash method success')
        return parseMediaData(mediaData, shortcode)
      }
    }
  } catch (e) {
    console.log('[SERVER DEBUG] query_hash method failed:', e)
  }

  return null
}

async function tryEmbedMethod(shortcode: string): Promise<PostData | null> {
  const embedUrl = `https://www.instagram.com/p/${shortcode}/embed/captioned/`
  const randomUA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)]

  console.log('[SERVER DEBUG] Trying embed method')

  const response = await fetch(embedUrl, {
    headers: {
      'User-Agent': randomUA,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'none',
    },
  })

  if (!response.ok) {
    console.log('[SERVER DEBUG] Embed method failed - response not ok')
    return null
  }

  const html = await response.text()

  // Try to find JSON data in the page
  const jsonMatch = html.match(/window\.__additionalDataLoaded\s*\(\s*['"][^'"]+['"]\s*,\s*(\{[\s\S]+?\})\s*\)\s*;/)
  if (jsonMatch) {
    try {
      const data = JSON.parse(jsonMatch[1])
      const mediaData = data?.shortcode_media || data?.graphql?.shortcode_media
      if (mediaData) {
        console.log('[SERVER DEBUG] Embed method - found JSON data')
        return parseMediaData(mediaData, shortcode)
      }
    } catch {}
  }

  // Fallback: parse HTML directly
  console.log('[SERVER DEBUG] Embed method - parsing HTML')
  return parseEmbedHtml(html, shortcode)
}

async function tryDirectMethod(shortcode: string): Promise<PostData | null> {
  console.log('[SERVER DEBUG] Trying direct method (?__a=1&__d=dis)')

  // Try the main Instagram page with different approaches
  const urls = [
    `https://www.instagram.com/p/${shortcode}/?__a=1&__d=dis`,
    `https://www.instagram.com/reel/${shortcode}/?__a=1&__d=dis`,
  ]

  // Use Instagram app user agent for better results
  const instagramUA = USER_AGENTS[3] // Instagram Android UA

  for (const url of urls) {
    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': instagramUA,
          'Accept': '*/*',
          'Accept-Language': 'en-US,en;q=0.9',
          'X-IG-App-ID': '936619743392459',
        },
      })

      if (response.ok) {
        const json = await response.json()
        const mediaData = json?.items?.[0] || json?.graphql?.shortcode_media
        if (mediaData) {
          console.log('[SERVER DEBUG] Direct method success')
          return parseMediaData(mediaData, shortcode)
        }
      }
    } catch (e) {
      console.log(`[SERVER DEBUG] Direct method failed for ${url}:`, e)
    }
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

  // Check for carousel using multiple detection methods
  const isCarousel = data.__typename === 'GraphSidecar' ||
                     data.product_type === 'carousel_container' ||
                     data.media_type === 8 ||
                     (data.edge_sidecar_to_children?.edges?.length || 0) > 0 ||
                     (data.carousel_media?.length || 0) > 0

  console.log('[SERVER DEBUG] parseMediaData:', {
    typename: data.__typename,
    product_type: data.product_type,
    isVideo,
    isCarousel,
    edgesCount: data.edge_sidecar_to_children?.edges?.length || 0,
    carouselCount: data.carousel_media?.length || 0
  })

  if (isCarousel) {
    // Handle carousel
    const edges = data.edge_sidecar_to_children?.edges || []
    const carouselMedia = data.carousel_media || []

    if (edges.length > 0) {
      edges.forEach((edge: any, idx: number) => {
        const node = edge.node
        if (!node) return

        const displayResources = Array.isArray(node.display_resources) ? node.display_resources : []
        const lastResource = displayResources.length > 0 ? displayResources[displayResources.length - 1] : null

        media.push({
          url: node.display_url || lastResource?.src,
          index: idx,
          is_video: node.is_video === true,
          video_url: node.video_url,
          thumbnail_url: node.display_url
        })
      })
    } else if (carouselMedia.length > 0) {
      carouselMedia.forEach((item: any, idx: number) => {
        if (!item) return

        // Handle different API response structures
        const candidates = Array.isArray(item.image_versions2?.candidates) ? item.image_versions2.candidates : []
        const videoVersions = Array.isArray(item.video_versions) ? item.video_versions : []
        const displayResources = Array.isArray(item.display_resources) ? item.display_resources : []
        const lastResource = displayResources.length > 0 ? displayResources[displayResources.length - 1] : null

        const imageUrl = item.display_url || (candidates.length > 0 ? candidates[0]?.url : undefined) || lastResource?.src
        const videoUrl = item.video_url || (videoVersions.length > 0 ? videoVersions[0]?.url : undefined)

        media.push({
          url: videoUrl || imageUrl,
          index: idx,
          is_video: item.is_video === true || item.media_type === 2,
          video_url: videoUrl,
          thumbnail_url: imageUrl
        })
      })
    }
  } else {
    // Single media
    const displayResources = Array.isArray(data.display_resources) ? data.display_resources : []
    const lastResource = displayResources.length > 0 ? displayResources[displayResources.length - 1] : null

    const imageUrl = data.display_url ||
                     data.image_versions2?.candidates?.[0]?.url ||
                     lastResource?.src
    const videoUrl = data.video_url || data.video_versions?.[0]?.url

    media.push({
      url: isVideo ? (videoUrl || imageUrl) : imageUrl,
      index: 0,
      is_video: isVideo,
      video_url: videoUrl,
      thumbnail_url: imageUrl
    })
  }

  console.log(`[SERVER DEBUG] Parsed ${media.length} media items`)

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
