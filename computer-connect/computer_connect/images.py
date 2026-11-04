"""Bounded in-memory desktop image decoding; no file or cache writes."""
from io import BytesIO
import warnings
from PIL import Image
from .transport import ConnectError
Image.MAX_IMAGE_PIXELS = 16_000_000

def decode_frame(data):
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > 16_000_000:
                raise ConnectError('Desktop image is too large.')
            return source.convert('RGB')

