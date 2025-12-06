import streamlit as st
import tempfile, os, sys, base64
from cv.depth_estimation import PostcardMaker
import streamlit.components.v1 as components

# --- Paths ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
cv_dir = os.path.join(parent_dir, 'cv')
sys.path.append(cv_dir)

STATIC_DIR = os.path.join(current_dir, "static_layers")
os.makedirs(STATIC_DIR, exist_ok=True)
pmaker = PostcardMaker(output_dir=STATIC_DIR)

# --- Streamlit config ---
st.set_page_config(page_title="Scrapbook Postcard", layout="wide")
st.markdown("<style>body {margin:0; overflow:hidden; background-color:#fef6e4;}</style>", unsafe_allow_html=True)

st.title("📬 Scrapbook Postcard Generator")
user_text = st.text_input("Add a message to your postcard:", key="msg_input")

# Optional stickers: hardcoded example
stickers = {
    "Heart": "https://i.imgur.com/9Zq9x6R.png",
    "Star": "https://i.imgur.com/l1fXJwO.png",
    "Flower": "https://i.imgur.com/1m3Z3uO.png"
}
selected_sticker = st.selectbox("Add a sticker:", ["None"] + list(stickers.keys()))

# --- Image upload ---
uploaded_file = st.file_uploader("Upload an image", type=["png","jpg","jpeg"], key="file_uploader")

if uploaded_file:
    # Loading animation
    loading = st.empty()
    loading.markdown("<h3 style='text-align:center;'>Processing your 3D scrapbook...</h3>", unsafe_allow_html=True)
    
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

        # --- Build full-screen scrapbook HTML ---
        html_layers = ""
        for i, layer_b64 in enumerate(layers_b64):
            scale = 1 - i * 0.03
            html_layers += f'''
            <img src="data:image/png;base64,{layer_b64}" class="layer"
                 style="position:absolute; top:0; left:0; width:100%; height:100%;
                        border:4px solid white; border-radius:12px;
                        box-shadow:0 4px 12px rgba(0,0,0,0.2);
                        z-index:{i+1}; transition: transform 0.2s; transform: scale({scale});">
            '''

        # Add user text
        text_html = ""
        if user_text:
            text_html = f'''
            <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);
                        color:#333; font-size:2em; font-family:'Patrick Hand', cursive;
                        text-align:center; pointer-events:none; z-index:100;">
                {user_text}
            </div>
            '''

        # Add sticker
        sticker_html = ""
        if selected_sticker != "None":
            sticker_url = stickers[selected_sticker]
            sticker_html = f'''
            <img src="{sticker_url}" style="position:absolute; top:20px; right:20px; width:80px; height:80px; z-index:101;">
            '''

        html_code = f"""
        <link href="https://fonts.googleapis.com/css2?family=Patrick+Hand&display=swap" rel="stylesheet">
        <div class="parallax-container" 
             style="position:fixed; top:0; left:0; width:100vw; height:100vh; overflow:hidden;">
            <img src="data:image/png;base64,{original_b64}" class="bg-layer"
                 style="width:100%; height:100%; object-fit:cover; position:absolute; top:0; left:0; z-index:0; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
            {html_layers}
            {text_html}
            {sticker_html}
            <button id="motion-btn" style="position:absolute; bottom:20px; left:20px; z-index:1000; padding:10px 15px; font-size:16px;">
                Enable Motion
            </button>
        </div>

        <script>
        const layers = document.querySelectorAll('.layer');
        const maxTranslate = 15;

        const handleMotion = (event) => {{
            const x = event.gamma || 0;
            const y = event.beta || 0;
            layers.forEach((layer, i) => {{
                const depth = (i + 1) / layers.length;
                const tx = Math.max(Math.min(x * depth, maxTranslate), -maxTranslate);
                const ty = Math.max(Math.min(y * depth, maxTranslate), -maxTranslate);
                const scale = 1 - i*0.03;
                layer.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ') rotate(' + (tx/20) + 'deg)';
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
