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

// Extract data from Instagram's embed page
async function getPostDataFromEmbed(shortcode: string): Promise<PostData> {
  const embedUrl = `https://www.instagram.com/p/${shortcode}/embed/captioned/`

  const response = await fetch(embedUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.5',
      'Cache-Control': 'no-cache',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch embed: ${response.status}`)
  }

  const html = await response.text()

  // Extract username
  const usernameMatch = html.match(/"username":"([^"]+)"/) ||
                        html.match(/class="UsernameText"[^>]*>([^<]+)</) ||
                        html.match(/@([a-zA-Z0-9._]+)/)
  const owner = usernameMatch ? usernameMatch[1] : 'unknown'

  // Extract caption
  const captionMatch = html.match(/"caption":"([^"]*)"/) ||
                       html.match(/class="Caption"[^>]*>.*?<span[^>]*>([^<]+)</)
  let caption = captionMatch ? captionMatch[1] : ''
  caption = caption.replace(/\\u[\dA-F]{4}/gi, (match) =>
    String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16))
  )
  caption = caption.replace(/\\n/g, '\n').replace(/\\"/g, '"')

  const media: MediaData[] = []

  // Check if it's a video/reel
  const isVideo = html.includes('"is_video":true') ||
                  html.includes('EmbeddedMediaVideo') ||
                  html.includes('video_url')

  const isReel = html.includes('"product_type":"clips"') ||
                 html.includes('"product_type":"reels"')

  // Extract video URLs
  const videoUrlMatches = html.matchAll(/"video_url":"([^"]+)"/g)
  for (const match of videoUrlMatches) {
    let videoUrl = match[1]
      .replace(/\\u0026/g, '&')
      .replace(/\\/g, '')

    // Find corresponding thumbnail
    const thumbnailMatch = html.match(/"display_url":"([^"]+)"/)
    const thumbnailUrl = thumbnailMatch
      ? thumbnailMatch[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
      : undefined

    if (!media.find(m => m.video_url === videoUrl)) {
      media.push({
        url: videoUrl,
        index: media.length,
        is_video: true,
        video_url: videoUrl,
        thumbnail_url: thumbnailUrl
      })
    }
  }

  // Extract images - Method 1: display_url in JSON
  const displayUrlMatches = html.matchAll(/"display_url":"([^"]+)"/g)
  for (const match of displayUrlMatches) {
    const url = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    // Skip if this is a thumbnail for a video we already have
    if (!media.find(m => m.url === url || m.thumbnail_url === url)) {
      media.push({
        url,
        index: media.length,
        is_video: false
      })
    }
  }

  // Method 2: EmbeddedMediaImage src
  const imgMatches = html.matchAll(/class="EmbeddedMediaImage"[^>]*src="([^"]+)"/g)
  for (const match of imgMatches) {
    const url = match[1].replace(/&amp;/g, '&')
    if (!media.find(m => m.url === url)) {
      media.push({
        url,
        index: media.length,
        is_video: false
      })
    }
  }

  // Method 3: srcset for high-res images
  const srcsetMatches = html.matchAll(/srcset="([^"]+)"/g)
  for (const match of srcsetMatches) {
    const srcset = match[1].replace(/&amp;/g, '&')
    const urls = srcset.split(',').map(s => s.trim().split(' ')[0])
    const highResUrl = urls[urls.length - 1]
    if (highResUrl && highResUrl.includes('cdninstagram') && !media.find(m => m.url === highResUrl)) {
      media.push({
        url: highResUrl,
        index: media.length,
        is_video: false
      })
    }
  }

  // Method 4: Direct image URLs (1080p)
  const directImgMatches = html.matchAll(/https:\/\/[^"'\s]+(?:cdninstagram|fbcdn)[^"'\s]+\.jpg[^"'\s]*/g)
  for (const match of directImgMatches) {
    let url = match[0].replace(/&amp;/g, '&').replace(/\\u0026/g, '&')
    url = url.split('"')[0].split("'")[0]
    if (!media.find(m => m.url === url) && url.includes('1080')) {
      media.push({
        url,
        index: media.length,
        is_video: false
      })
    }
  }

  // Method 5: Direct video URLs (.mp4)
  const directVideoMatches = html.matchAll(/https:\/\/[^"'\s]+(?:cdninstagram|fbcdn)[^"'\s]+\.mp4[^"'\s]*/g)
  for (const match of directVideoMatches) {
    let url = match[0].replace(/&amp;/g, '&').replace(/\\u0026/g, '&')
    url = url.split('"')[0].split("'")[0]
    if (!media.find(m => m.url === url || m.video_url === url)) {
      media.push({
        url,
        index: media.length,
        is_video: true,
        video_url: url
      })
    }
  }

  // Detect carousel
  const isCarousel = media.filter(m => !m.is_video || isReel).length > 1 ||
                     html.includes('edge_sidecar_to_children') ||
                     html.includes('GraphSidecar')

  // If no media found but it's a video, try alternative extraction
  if (media.length === 0 && isVideo) {
    // Try to get video from script tags
    const scriptMatch = html.match(/window\.__additionalDataLoaded\([^,]+,\s*({.+?})\s*\);/)
    if (scriptMatch) {
      try {
        const data = JSON.parse(scriptMatch[1])
        const videoUrl = data?.shortcode_media?.video_url
        if (videoUrl) {
          media.push({
            url: videoUrl,
            index: 0,
            is_video: true,
            video_url: videoUrl,
            thumbnail_url: data?.shortcode_media?.display_url
          })
        }
      } catch {
        // JSON parse failed, continue
      }
    }
  }

  if (media.length === 0) {
    throw new Error('No se encontró contenido. El post puede ser privado o no disponible.')
  }

  // Deduplicate and clean media
  const uniqueMedia = media.reduce((acc: MediaData[], item) => {
    // Skip thumbnails and very small images
    if (item.url.includes('s150x150') || item.url.includes('s320x320')) {
      return acc
    }
    if (!acc.find(i => i.url === item.url)) {
      acc.push({ ...item, index: acc.length })
    }
    return acc
  }, [])

  return {
    success: true,
    shortcode,
    owner,
    caption,
    media: uniqueMedia.length > 0 ? uniqueMedia : media,
    is_carousel: isCarousel,
    is_reel: isReel || (isVideo && !isCarousel),
  }
}

// Fallback: Use Instagram's oEmbed API
async function getPostDataFromOEmbed(shortcode: string): Promise<Partial<PostData>> {
  const oembedUrl = `https://api.instagram.com/oembed/?url=https://www.instagram.com/p/${shortcode}/`

  try {
    const response = await fetch(oembedUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
      },
    })

    if (!response.ok) {
      return {}
    }

    const data = await response.json()

    return {
      owner: data.author_name || 'unknown',
      caption: data.title || '',
    }
  } catch {
    return {}
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
    const postData = await getPostDataFromEmbed(shortcode)

    // Enrich with oEmbed data if needed
    if (postData.owner === 'unknown' || !postData.caption) {
      const oembedData = await getPostDataFromOEmbed(shortcode)
      if (oembedData.owner && postData.owner === 'unknown') {
        postData.owner = oembedData.owner
      }
      if (oembedData.caption && !postData.caption) {
        postData.caption = oembedData.caption
      }
    }

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
