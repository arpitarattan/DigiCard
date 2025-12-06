import streamlit as st
import tempfile, os, sys, base64
from cv.depth_estimation import PostcardMaker
import streamlit.components.v1 as components
import time

# --- Paths ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
cv_dir = os.path.join(parent_dir, 'cv')
sys.path.append(cv_dir)

STATIC_DIR = os.path.join(current_dir, "static_layers")
os.makedirs(STATIC_DIR, exist_ok=True)
pmaker = PostcardMaker(output_dir=STATIC_DIR)

# --- Streamlit config ---
st.set_page_config(page_title="3D Postcard Generator", layout="wide")
st.markdown("<style>body {margin:0; overflow:hidden;}</style>", unsafe_allow_html=True)

# --- Image upload ---
uploaded_file = st.file_uploader("Upload an image", type=["png","jpg","jpeg"], key="file_uploader")

if uploaded_file:
    # Show loading animation
    loading = st.empty()
    loading.markdown("<h3 style='text-align:center;'>Processing your 3D postcard...</h3>", unsafe_allow_html=True)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        # Process depth layers
        package = pmaker.convert_image(image_path=tmp_path)

        def get_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        original_path = os.path.join(STATIC_DIR, "images", os.path.basename(package["original"]))
        layers = [os.path.join(STATIC_DIR, "images", os.path.basename(p['image_url'])) for p in package["layers"]]

        original_b64 = get_base64(original_path)
        layers_b64 = [get_base64(layer) for layer in layers]

        # Hide uploader/loading
        loading.empty()
        st.empty()

        # --- Full screen gyro postcard ---
        html_layers = ""
        for i, layer_b64 in enumerate(layers_b64):
            html_layers += f'''
            <img src="data:image/png;base64,{layer_b64}" class="layer" 
                 style="position:absolute; top:0; left:0; width:100%; height:100%;
                        z-index:{i+1}; transition: transform 0.2s;">
            '''

        html_code = f"""
        <div class="parallax-container" 
             style="position:fixed; top:0; left:0; width:100vw; height:100vh; overflow:hidden;">
            <img src="data:image/png;base64,{original_b64}" class="bg-layer" 
                 style="width:100%; height:100%; object-fit:cover; position:absolute; top:0; left:0; z-index:0;">
            {html_layers}
            <button id="motion-btn" style="position:absolute; bottom:20px; left:20px; z-index:1000; padding:10px 15px; font-size:16px;">
                Enable Motion
            </button>
        </div>

        <script>
        const layers = document.querySelectorAll('.layer');
        const maxTranslate = 10; // limit motion to ±10px
        const transitionTime = 0.2; // smooth transition in seconds

        const handleMotion = (event) => {{
            const x = event.gamma || 0;
            const y = event.beta || 0;
            layers.forEach((layer, i) => {{
                const depth = (i + 1) / layers.length;
                const tx = Math.max(Math.min(x * depth, maxTranslate), -maxTranslate);
                const ty = Math.max(Math.min(y * depth, maxTranslate), -maxTranslate);
                layer.style.transform = 'translate(' + tx + 'px,' + ty + 'px)';
            }});
        }};

        if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission === 'function') {{
            document.getElementById("motion-btn").onclick = () => {{
                DeviceOrientationEvent.requestPermission()
                    .then(permissionState => {{
                        if (permissionState === "granted") {{
                            window.addEventListener("deviceorientation", handleMotion);
                            document.getElementById("motion-btn").style.display = "none";
                        }} else {{
                            alert("Permission denied");
                        }}
                    }})
                    .catch(console.error);
            }};
        }} else {{
            window.addEventListener("deviceorientation", handleMotion);
            document.getElementById("motion-btn").style.display = "none";
        }}
        </script>
        """

        components.html(html_code, height=800)

    finally:
        os.unlink(tmp_path)
