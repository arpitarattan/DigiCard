from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn,tempfile, os, sys

# Add the 'cv' path to dir
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
cv_dir = os.path.join(parent_dir, 'cv')
sys.path.append(cv_dir)

# Now, import the function
from depth_estimation import PostcardMaker

# Create FastAPI app
app = FastAPI(title="3D Postcard Server")

# Allow frontend (React) to talk to backend (FastAPI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(current_dir, "static_layers")
IMAGES_DIR = os.path.join(STATIC_DIR, "images")

os.makedirs(IMAGES_DIR, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Pass STATIC_DIR to PostcardMaker
pmaker = PostcardMaker(output_dir=STATIC_DIR)

@app.post("/process-depth")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
        
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.write(await file.read())
    tmp_path = tmp.name
    tmp.close()
    
    try:
        package = pmaker.convert_image(image_path=tmp_path)
        return {
            "original": package["original"],
            "layers": package["layers"]
        }

    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
