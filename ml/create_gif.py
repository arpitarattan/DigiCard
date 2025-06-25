import cv2
import numpy as np
from PIL import Image
import imageio
import base64
import io
import json
from depth_estimation import PostcardMaker

# def decode_base64_image(b64_string: str) -> np.ndarray:
#     """Convert base64-encoded image to OpenCV format"""
#     if b64_string.startswith("data:image"):
#         b64_string = b64_string.split(",")[1]
#     img_data = base64.b64decode(b64_string)
#     image = Image.open(io.BytesIO(img_data))
#     return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

def shift_layer(image: np.ndarray, dx: int) -> np.ndarray:
    """Translate image horizontally"""
    rows, cols = image.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, 0]])
    shifted = cv2.warpAffine(image, M, (cols, rows), borderMode=cv2.BORDER_REFLECT)
    return shifted

def create_wiggle_animation(layers: list, steps=8, max_shift=15) -> Image:
    """Create a looping wiggle animation from depth layers"""
    frames = []
    directions = list(range(0, max_shift, max_shift // steps)) + list(range(max_shift, -1, -max_shift // steps))
    
    for shift in directions:
        frame = np.zeros_like(cv2.imread(layers[0]['image_url']))
        
        # Render layers from back to front
        for layer in layers:
            img_url = layer['image_url']
            img = cv2.cvtColor(cv2.imread(img_url), cv2.COLOR_BGR2RGB)
            depth = layer['depth']
            scaled_shift = int(shift * (1 - depth))  # Foreground shifts more
            shifted_img = shift_layer(img, scaled_shift)
            frame = np.where(shifted_img > 0, shifted_img, frame)
        
        pil_frame = Image.fromarray(frame)
        frames.append(pil_frame)

    # Make it loop smoothly
    frames += frames[::-1]
    
    return frames

def save_gif(frames, output_path="wiggle.gif", duration=60):
    """Save frames to animated GIF"""
    frames[0].save(output_path, save_all=True, append_images=frames[1:], loop=0, duration=duration)
    print(f"Wiggle GIF saved to {output_path}")

# Example usage:
image_path = 'assets\istockphoto-1381637603-612x612.jpg'
    
generator = PostcardMaker()
result = generator.convert_image(image_path= image_path)

layers = result["layers"]
frames = create_wiggle_animation(layers, steps=6, max_shift=20)
save_gif(frames, "wiggle.gif")
