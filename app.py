import streamlit as st
import tempfile, os, sys, base64
from cv.depth_estimation import PostcardMaker

# --- Paths ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
cv_dir = os.path.join(parent_dir, 'cv')
sys.path.append(cv_dir)

STATIC_DIR = os.path.join(current_dir, "static_layers")
os.makedirs(STATIC_DIR, exist_ok=True)
pmaker = PostcardMaker(output_dir=STATIC_DIR)

st.set_page_config(page_title="3D Postcard Generator", layout="wide")
st.title("3D Postcard Generator")

uploaded_file = st.file_uploader("Upload an image", type=["png","jpg","jpeg"])
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        package = pmaker.convert_image(image_path=tmp_path)

        def get_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        layers = [os.path.join(STATIC_DIR, "images", os.path.basename(p['image_url'])) for p in package["layers"]]

        # Prepare HTML with base64 images and scaling
        html_layers = ""
        total_layers = len(layers)
        for i, layer in enumerate(layers):
            b64 = get_base64(layer)
            scale = 1 - i * 0.05  # slightly smaller for background layers
            z = total_layers - i
            html_layers += f'''
            <img src="data:image/png;base64,{b64}" 
                 style="position:absolute; top:0; left:0; width:100%; height:100%;
                        transform: scale({scale});
                        transform-origin: center center;
                        transition: transform 0.1s;
                        z-index:{z};">
            '''

        html_code = f"""
        <div id="parallax-container" style="position: relative; width: 100%; height: 400px; overflow: hidden;">
            {html_layers}
        </div>
        <script>
        const layers = document.querySelectorAll('#parallax-container img');
        const maxTranslate = 20; // max px movement
        window.addEventListener('deviceorientation', function(event) {{
            let x = event.gamma || 0; // left-right tilt
            let y = event.beta || 0;  // front-back tilt
            layers.forEach((layer, i) => {{
                let depth = (i+1) / layers.length; // scale per layer
                let tx = Math.max(Math.min(x*depth, maxTranslate), -maxTranslate);
                let ty = Math.max(Math.min(y*depth, maxTranslate), -maxTranslate);
                layer.style.transform = 'translate(' + tx + 'px,' + ty + 'px)' + 
                                        ' scale(' + (1 - i*0.05) + ')';
            }});
        }});
        </script>
        """

        import streamlit.components.v1 as components
        components.html(html_code, height=400)

    finally:
        os.unlink(tmp_path)
