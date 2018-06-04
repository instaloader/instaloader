from io import BytesIO

from requests import get
from PIL import Image, ImageDraw
from instaloader import *

L = Instaloader()

# Load Post instance
post = load_structure_from_file(L.context, '2017-10-01_18-53-03_UTC.json.xz')
# or post = Post.from_shortcode(L.context, SHORTCODE)

# Render caption
image = Image.open(BytesIO(get(post.url).content))
draw = ImageDraw.Draw(image)
color = 'rgb(0, 0, 0)'  # black color
draw.text((300,100), post.caption.encode('latin1', errors='ignore'), fill=color)

# Save image
image.save('test.jpg')
