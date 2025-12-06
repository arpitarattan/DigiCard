import streamlit as st
import tempfile, os, sys, base64
from cv.depth_estimation import PostcardMaker
import streamlit.components.v1 as components
import urllib.parse
import uuid

# --- Paths ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
cv_dir = os.path.join(parent_dir, 'cv')
sys.path.append(cv_dir)

STATIC_DIR = os.path.join(current_dir, "static_layers")
os.makedirs(STATIC_DIR, exist_ok=True)
pmaker = PostcardMaker(output_dir=STATIC_DIR)

# --- Streamlit config ---
st.set_page_config(page_title="DigiCard", layout="wide")
st.markdown("<style>body {margin:0; overflow:hidden; background-color:#f5e6d2;}</style>", unsafe_allow_html=True)

st.markdown("""
<h1 style="font-family:'Press Start 2P', cursive; text-align:center; color:#a0522d; margin-top:20px;">
DigiCard
</h1>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# --- Handle URL parameters ---
query_params = st.experimental_get_query_params()
shared_id = query_params.get("id", [None])[0]

if shared_id:
    # Decode saved postcard from session state or a temp storage (simplified: use session_state)
    saved = st.session_state.get(f"card_{shared_id}", None)
    if saved:
        original_b64 = saved["original"]
        layers_b64 = saved["layers"]
        user_text = saved["text"]
    else:
        st.error("This postcard does not exist.")
        st.stop()
else:
    uploaded_file = st.file_uploader("Upload an image", type=["png","jpg","jpeg"])
    user_text = st.text_input("Add your postcard message:")

    if uploaded_file and user_text:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        package = pmaker.convert_image(image_path=tmp_path)
        os.unlink(tmp_path)

        def get_base64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        original_path = os.path.join(STATIC_DIR, "images", os.path.basename(package["original"]))
        layers = [os.path.join(STATIC_DIR, "images", os.path.basename(p['image_url'])) for p in package["layers"]]

        original_b64 = get_base64(original_path)
        layers_b64 = [get_base64(layer) for layer in layers]

        # Save to session_state for sharing
        shared_id = str(uuid.uuid4())
        st.session_state[f"card_{shared_id}"] = {
            "original": original_b64,
            "layers": layers_b64,
            "text": user_text
        }

        # Generate shareable link
        share_url = f"{st.get_url()}?id={shared_id}"
        st.success(f"Share your postcard with this link: {share_url}")

# --- Display postcard ---
if shared_id:
    html_layers = ""
    for i, layer_b64 in enumerate(layers_b64):
        scale = 1 - i * 0.03
        html_layers += f'''
        <img src="data:image/png;base64,{layer_b64}" class="layer"
             style="position:absolute; top:0; left:0; width:100%; height:100%;
                    border-radius:12px; z-index:{i+1}; transition: transform 0.2s; transform: scale({scale});">
        '''

    text_html = ""
    if user_text:
        text_html = f'''
        <div id="user-text" style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);
                    color:#333; font-size:2em; font-family:'Patrick Hand', cursive;
                    text-align:center; z-index:100;">
            {user_text}
        </div>
        '''

    html_code = f"""
    <link href="https://fonts.googleapis.com/css2?family=Patrick+Hand&display=swap" rel="stylesheet">
    <div class="parallax-container" style="position:fixed; top:0; left:0; width:100vw; height:100vh;
         display:flex; justify-content:center; align-items:center;">
        <div id="card" style="position:relative; width:90vw; height:90vh; background:white; 
             border-radius:12px; box-shadow:0 8px 24px rgba(0,0,0,0.25); overflow:hidden;">
            <img src="data:image/png;base64,{original_b64}" style="width:100%; height:100%; object-fit:cover; border-radius:12px; position:absolute; top:0; left:0; z-index:0;">
            {html_layers}
            {text_html}
        </div>

        <button id="motion-btn" style="position:absolute; bottom:20px; left:20px; z-index:1000; padding:10px 15px; font-size:16px;">
            Enable Motion
        </button>
    </div>

    <script>
    const card = document.getElementById('card');
    const layers = document.querySelectorAll('.layer');
    const maxTranslate = 15;

    const handleMotion = (event) => {{
        const gyroX = event.gamma || 0;
        const gyroY = event.beta || 0;
        layers.forEach((layer, i) => {{
            const depth = (i + 1) / layers.length;
            let tx = gyroX * depth;
            let ty = gyroY * depth;

            const maxX = (card.clientWidth - layer.clientWidth)/2 + maxTranslate;
            const maxY = (card.clientHeight - layer.clientHeight)/2 + maxTranslate;
            tx = Math.max(Math.min(tx, maxX), -maxX);
            ty = Math.max(Math.min(ty, maxY), -maxY);

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
