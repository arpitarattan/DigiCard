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
st.set_page_config(page_title="DigiCard", layout="wide")
st.markdown("<style>body {margin:0; overflow:hidden; background-color:#ffc0cb;}</style>", unsafe_allow_html=True)

st.markdown("""
<h1 style="font-family:'Amatic SC', cursive; text-align:center; color:#ff69b4; margin-top:20px; font-size:3em;">
DigiCard
</h1>
<link href="https://fonts.googleapis.com/css2?family=Amatic+SC:wght@700&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# --- User input ---
uploaded_file = st.file_uploader("Upload an image for your postcard:", type=["png","jpg","jpeg"])
user_text = st.text_input("Add your postcard message:")

if uploaded_file and user_text:
    loading = st.empty()
    loading.markdown("<h3 style='text-align:center;'>Processing your 3D postcard...</h3>", unsafe_allow_html=True)

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

    loading.empty()
    st.empty()

    html_layers = ""
    for i, layer_b64 in enumerate(layers_b64):
        scale = 1 - i * 0.03
        html_layers += f'''
        <img src="data:image/png;base64,{layer_b64}" class="layer"
             style="position:absolute; top:0; left:0; width:100%; height:100%;
                    border-radius:12px; z-index:{i+1}; transition: transform 0.2s; transform: scale({scale});">
        '''

    # Span text across the whole card
    text_html = f'''
    <div id="user-text" style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);
                color:#fff; font-size:3em; font-family:'Amatic SC', cursive;
                text-align:center; width:90%; z-index:100; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
        {user_text}
    </div>
    '''

    html_code = f"""
    <link href="https://fonts.googleapis.com/css2?family=Amatic+SC:wght@700&display=swap" rel="stylesheet">

    <div class="parallax-container" style="position:fixed; top:0; left:0; width:100vw; height:100vh;
         display:flex; justify-content:center; align-items:center;">
        <!-- Horizontal postcard -->
        <div id="card" style="position:relative; width:95vw; height:55vw; max-height:80vh; background:white; 
             border-radius:12px; box-shadow:0 8px 24px rgba(0,0,0,0.25); overflow:hidden; display:flex; justify-content:center; align-items:center;">
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
