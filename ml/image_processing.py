import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
import io
import base64
from typing import List, Tuple, Dict
import json

class DepthEstimator:
    def __init__(self):
        """Initialize depth estimation with optimized parameters for mobile photos"""
        self.num_layers = 3  # Background, middle, foreground
        self.blur_kernels = [(15, 15), (9, 9), (5, 5)]  # Stronger blur for mobile
        
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Optimize image for depth detection"""
        # Resize if too large (mobile photos can be huge)
        height, width = image.shape[:2]
        if width > 1200:
            scale = 1200 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Enhance contrast for better depth cues
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(l)
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    def detect_horizon_line(self, image: np.ndarray) -> int:
        """Detect horizon for landscape photos - key for good depth layers"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use Hough lines to find strong horizontal lines (horizon)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        horizon_y = image.shape[0] // 3  # Default to upper third
        
        if lines is not None:
            horizontal_lines = []
            for rho, theta in lines[:10]:  # Check top 10 lines
                if abs(theta - np.pi/2) < 0.2:  # Nearly horizontal
                    y = int(rho / np.sin(theta)) if np.sin(theta) != 0 else horizon_y
                    if 0.2 * image.shape[0] < y < 0.6 * image.shape[0]:  # Reasonable horizon position
                        horizontal_lines.append(y)
            
            if horizontal_lines:
                horizon_y = int(np.median(horizontal_lines))
        
        return horizon_y
    
    def create_depth_mask(self, image: np.ndarray, layer_idx: int, horizon_y: int) -> np.ndarray:
        """Create mask for specific depth layer using multiple cues"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # 1. Distance-based mask (perspective)
        distance_mask = np.zeros_like(gray, dtype=np.float32)
        for y in range(height):
            # Exponential falloff from bottom (foreground) to horizon
            if y > horizon_y:
                distance_factor = (y - horizon_y) / (height - horizon_y)
            else:
                distance_factor = 0.1  # Sky/background
            distance_mask[y, :] = distance_factor
        
        # 2. Focus/sharpness mask
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = np.abs(laplacian).astype(np.float32)
        sharpness = cv2.GaussianBlur(sharpness, (5, 5), 0)
        sharpness = sharpness / (sharpness.max() + 1e-6)
        
        # 3. Edge density (objects in foreground have more edges)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = cv2.GaussianBlur(edges.astype(np.float32), (15, 15), 0)
        edge_density = edge_density / (edge_density.max() + 1e-6)
        
        # 4. Color saturation (foreground often more saturated)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].astype(np.float32) / 255.0
        
        # Combine all cues
        combined_depth = (
            distance_mask * 0.4 +
            sharpness * 0.3 +
            edge_density * 0.2 +
            saturation * 0.1
        )
        
        # Create layer-specific mask
        if layer_idx == 0:  # Background
            mask = (combined_depth < 0.3).astype(np.uint8) * 255
        elif layer_idx == 1:  # Middle
            mask = ((combined_depth >= 0.3) & (combined_depth < 0.7)).astype(np.uint8) * 255
        else:  # Foreground
            mask = (combined_depth >= 0.7).astype(np.uint8) * 255
        
        # Smooth the mask
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
        mask = cv2.GaussianBlur(mask, (3, 3), 0)
        
        return mask
    
    def extract_layer(self, image: np.ndarray, mask: np.ndarray, layer_idx: int) -> np.ndarray:
        """Extract and enhance a specific depth layer"""
        # Apply mask
        masked_image = image.copy()
        mask_3ch = cv2.merge([mask, mask, mask]) / 255.0
        masked_image = (masked_image * mask_3ch).astype(np.uint8)
        
        # Add subtle effects based on depth
        if layer_idx == 0:  # Background - slightly desaturated and cooler
            hsv = cv2.cvtColor(masked_image, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] *= 0.8  # Reduce saturation
            hsv[:, :, 0] = np.where(hsv[:, :, 0] > 0, hsv[:, :, 0] + 10, hsv[:, :, 0])  # Cooler hue
            masked_image = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        elif layer_idx == 2:  # Foreground - slightly enhanced
            enhanced = cv2.convertScaleAbs(masked_image, alpha=1.1, beta=5)
            masked_image = np.where(mask_3ch > 0.5, enhanced, masked_image).astype(np.uint8)
        
        return masked_image
    
    def process_image(self, image_path: str) -> Dict:
        """Main processing function - returns layered depth data"""
        # Load and preprocess
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        original_image = image.copy()
        image = self.preprocess_image(image)
        
        # Detect horizon for better landscape depth
        horizon_y = self.detect_horizon_line(image)
        
        # Generate layers
        layers = []
        depth_values = [0.9, 0.5, 0.1]  # Far to near
        
        for i in range(self.num_layers):
            # Create depth mask
            mask = self.create_depth_mask(image, i, horizon_y)
            
            # Extract layer
            layer_image = self.extract_layer(image, mask, i)
            
            # Convert to base64 for frontend
            _, buffer = cv2.imencode('.jpg', layer_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            layer_b64 = base64.b64encode(buffer).decode('utf-8')
            
            layers.append({
                'image': f"data:image/jpeg;base64,{layer_b64}",
                'depth': depth_values[i],
                'name': ['background', 'midground', 'foreground'][i],
                'scale': 1.0 + (i * 0.05)  # Slight scale difference
            })
        
        # Convert original for reference
        _, orig_buffer = cv2.imencode('.jpg', original_image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        original_b64 = base64.b64encode(orig_buffer).decode('utf-8')
        
        return {
            'layers': layers,
            'original': f"data:image/jpeg;base64,{original_b64}",
            'horizon_y': horizon_y,
            'image_dimensions': {
                'width': image.shape[1],
                'height': image.shape[0]
            }
        }

# FastAPI integration
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os

app = FastAPI(title="3D Postcard Depth Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

depth_estimator = DepthEstimator()

@app.post("/process-depth")
async def process_depth(file: UploadFile = File(...)):
    """Process uploaded image and return depth layers"""
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Process the image
        result = depth_estimator.process_image(tmp_path)
        return {
            "success": True,
            "data": result,
            "filename": file.filename
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "3D Postcard Depth Estimation"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)