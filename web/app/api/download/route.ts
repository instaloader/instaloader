import { NextRequest, NextResponse } from 'next/server'

interface ImageData {
  url: string
  index: number
  is_video: boolean
}

interface PostData {
  success: boolean
  shortcode: string
  owner: string
  caption: string
  images: ImageData[]
  is_carousel: boolean
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
  // Decode unicode escapes
  caption = caption.replace(/\\u[\dA-F]{4}/gi, (match) =>
    String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16))
  )
  caption = caption.replace(/\\n/g, '\n').replace(/\\"/g, '"')

  // Extract images - multiple methods
  const images: ImageData[] = []

  // Method 1: Look for display_url in JSON data
  const displayUrlMatches = html.matchAll(/"display_url":"([^"]+)"/g)
  for (const match of displayUrlMatches) {
    const url = match[1].replace(/\\u0026/g, '&').replace(/\\/g, '')
    if (!images.find(img => img.url === url)) {
      images.push({
        url,
        index: images.length,
        is_video: false
      })
    }
  }

  // Method 2: Look for src in img tags with EmbeddedMedia
  const imgMatches = html.matchAll(/class="EmbeddedMediaImage"[^>]*src="([^"]+)"/g)
  for (const match of imgMatches) {
    const url = match[1].replace(/&amp;/g, '&')
    if (!images.find(img => img.url === url)) {
      images.push({
        url,
        index: images.length,
        is_video: false
      })
    }
  }

  // Method 3: Look for srcset in img tags
  const srcsetMatches = html.matchAll(/srcset="([^"]+)"/g)
  for (const match of srcsetMatches) {
    // Get the highest resolution from srcset
    const srcset = match[1].replace(/&amp;/g, '&')
    const urls = srcset.split(',').map(s => s.trim().split(' ')[0])
    const highResUrl = urls[urls.length - 1]
    if (highResUrl && highResUrl.includes('cdninstagram') && !images.find(img => img.url === highResUrl)) {
      images.push({
        url: highResUrl,
        index: images.length,
        is_video: false
      })
    }
  }

  // Method 4: Direct image URLs from content
  const directImgMatches = html.matchAll(/https:\/\/[^"'\s]+(?:cdninstagram|fbcdn)[^"'\s]+\.jpg[^"'\s]*/g)
  for (const match of directImgMatches) {
    let url = match[0].replace(/&amp;/g, '&').replace(/\\u0026/g, '&')
    // Clean up the URL
    url = url.split('"')[0].split("'")[0]
    if (!images.find(img => img.url === url) && url.includes('1080')) {
      images.push({
        url,
        index: images.length,
        is_video: false
      })
    }
  }

  // Check for videos
  const isVideo = html.includes('"is_video":true') || html.includes('EmbeddedMediaVideo')

  // Detect carousel
  const isCarousel = images.length > 1 || html.includes('edge_sidecar_to_children') || html.includes('GraphSidecar')

  if (images.length === 0) {
    throw new Error('No images found in the post. The post might be private or unavailable.')
  }

  // Deduplicate and clean images
  const uniqueImages = images.reduce((acc: ImageData[], img) => {
    // Skip thumbnails and very small images
    if (img.url.includes('s150x150') || img.url.includes('s320x320')) {
      return acc
    }
    if (!acc.find(i => i.url === img.url)) {
      acc.push({ ...img, index: acc.length })
    }
    return acc
  }, [])

  return {
    success: true,
    shortcode,
    owner,
    caption,
    images: uniqueImages.length > 0 ? uniqueImages : images,
    is_carousel: isCarousel,
  }
}

// Fallback: Use Instagram's oEmbed API for basic info
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

  // Validate shortcode
  if (!shortcode) {
    return NextResponse.json(
      { success: false, error: 'Shortcode is required' },
      { status: 400 }
    )
  }

  // Validate shortcode format
  if (!/^[A-Za-z0-9_-]+$/.test(shortcode)) {
    return NextResponse.json(
      { success: false, error: 'Invalid shortcode format' },
      { status: 400 }
    )
  }

  try {
    // Try to get data from embed
    const postData = await getPostDataFromEmbed(shortcode)

    // Optionally enrich with oEmbed data
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
          : 'Failed to fetch post data. The post might be private or unavailable.',
        shortcode,
        owner: '',
        caption: '',
        images: [],
        is_carousel: false,
      },
      { status: 500 }
    )
  }
}
