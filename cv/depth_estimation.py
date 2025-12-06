'''
Take in Images, perform create 3D lenticular effect from them
'''
import cv2, os, base64
import numpy as np
from PIL import Image

class PostcardMaker:
    def __init__(self, output_dir="static_layers"):
        self.num_layers = 3 # Number of parallax layers
        self.output_dir = os.path.join(output_dir, 'images')

    def preprocess_image(self, image):
        '''
        Convert image from phone to compatible size with more constrast for depth estimation
        '''    
        h, w = image.shape[:2]

        # scale image down if too large
        if w > 1200:
            scale = 1200 / w
            w, h = int(w * scale), int(h * scale)
            image = cv2.resize(image, (w,h), interpolation= cv2.INTER_AREA)

        # Enhance constrast for better depth estimation
        l,a,b = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2LAB))
        l = cv2.createCLAHE(clipLimit=10.0, tileGridSize=(16,16)).apply(l) # Enhance image by CLAHE
        enhanced = cv2.merge([l, a, b])
        return image, cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)

    def detect_horizon_line(self, image: np.ndarray) -> int:
        '''
        Detect horizon line in photo to determine fore/mid/background using canny edge detecton and hough transforms
        '''
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use Hough lines to find strong horizontal lines (horizon)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        horizon_y = image.shape[0] // 3  # Default to upper third

        if lines is not None:
            horizontal_lines = []
            for r_theta in lines[:10]:  # Check top 10 lines
                arr = np.array(r_theta[0], dtype=np.float64)
                rho, theta = arr
                if abs(theta - np.pi/2) < 0.2:  # Nearly horizontal
                    y = int(rho / np.sin(theta)) if np.sin(theta) != 0 else horizon_y
                    if 0.2 * image.shape[0] < y < 0.6 * image.shape[0]:  # Reasonable horizon position
                        horizontal_lines.append(y)
            
            if horizontal_lines:
                horizon_y = int(np.median(horizontal_lines))        
        return horizon_y

    def get_distance_mask(self, gray, horizon_y, ):
        '''
        Use distance relative to horizon to get back/foreground
        '''
        height, width = gray.shape
        distance_mask = np.zeros_like(gray, dtype=np.float32)
        for y in range(height):
            # Exponential falloff from bottom (foreground) to horizon
            if y > horizon_y:
                distance_factor = (y - horizon_y) / (height - horizon_y)
            else:
                distance_factor = 0.1  # Sky/background
            distance_mask[y, :] = distance_factor
        return distance_mask

    def create_depth_masks(self, image: np.ndarray, horizon_y: int) -> np.ndarray:
        '''
        Create mask based on layer (foreground, mid, back) using visual cues (distance, sharpness, edge, color)
        '''
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 1. Distance-based mask (perspective)
        distance_mask= self.get_distance_mask(gray, horizon_y)
        
        # 2. Focus/sharpness mask
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = np.abs(laplacian).astype(np.float32)
        sharpness = cv2.GaussianBlur(sharpness, (5, 5), 0)
        sharpness = sharpness / (sharpness.max() + 1e-6)
       
        # 3. Edge density (objects in foreground have more edges)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = cv2.GaussianBlur(edges.astype(np.float32), (15, 15), 0)
        edge_density = edge_density / (edge_density.max() + 1e-6)
       
        # 4. Color saturation
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].astype(np.float32) / 255.0
        
        # Combine all cues
        combined_depth = (
            distance_mask * 0.4 +
            sharpness * 0.3 +
            edge_density * 0.3 +
            saturation * 0.2 
        )
        
        # Create layer-specific masks
        background = (combined_depth < 0.3).astype(np.uint8) * 255
        midground = ((combined_depth >= 0.3) & (combined_depth < 0.7)).astype(np.uint8) * 255
        foreground = (combined_depth >= 0.7).astype(np.uint8) * 255
        
        # Smooth the masks
        background = self.smooth_mask(background)
        midground = self.smooth_mask(midground)
        foreground = self.smooth_mask(foreground)
        
        return [background, midground, foreground]

    def smooth_mask(self, mask):
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
        mask = cv2.GaussianBlur(mask, (7, 7), sigmaX=3, sigmaY=3)
        return mask

    def extract_layer(self, image, mask, layer_idx) -> np.ndarray:
        '''
        Extract layer from image using mask
        '''
        # Apply mask
        masked_image = image.copy()

        # Make it 4 channel to avoid black outlines in layers
        masked_image = cv2.merge([
            masked_image[..., 0],
            masked_image[..., 1],
            masked_image[..., 2],
            mask
        ])
                   
        if layer_idx == 2:  # Foreground - slightly enhanced
            enhanced = cv2.convertScaleAbs(masked_image, alpha=1.1, beta=5)
            masked_image = np.where(masked_image > 0.5, enhanced, masked_image).astype(np.uint8)
        
        return masked_image

    def convert_image(self, image_path):
        '''
        Main utility function to take in image path and convert to 3d postcard layers 
        Returns: self.num_layers number of layers extracted from image
        '''
        image = cv2.imread(image_path)
        original_image = image.copy()

        # Preprocess image and detect horizon line
        image, enhanced = self.preprocess_image(image)
        horizon_y = self.detect_horizon_line(enhanced)

        # Generate masks
        masks = self.create_depth_masks(image, horizon_y) # Get different layer masks [back, mid, fore]
        layers = []

        depth_values = [1, 0.7, 0.5] # Far to nea

        # Clean up old layers
        for file in os.listdir(self.output_dir):
            if file.startswith("layer_") and file.endswith(".png"):
                os.remove(os.path.join(self.output_dir, file))

        # Extract layers
        cv2.imwrite(os.path.join(self.output_dir, 'layer_og.png'), original_image) # Save original

        for i in range(self.num_layers):
            layer_image = self.extract_layer(image, masks[i], layer_idx = i)
            layer_image = np.clip(layer_image, 0, 255).astype(np.uint8)

            layer_filename = f"layer_{i}.png"
            layer_path = os.path.join(self.output_dir, layer_filename)
            cv2.imwrite(layer_path, layer_image)

            print(f'Saved layer{i}')

            layers.append({
                'image_url': f"/images/layer_{i}.png",
                'depth': depth_values[i]
            })
        
        return {
            'layers': layers,
            'original': f"/images/layer_og.png",
        }

# if __name__ == '__main__':
#     image_path = 'assets\istockphoto-1381637603-612x612.jpg'
#     generator = PostcardMaker()
#     package = generator.convert_image(image_path= image_path)
