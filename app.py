import streamlit as st
import tempfile, os, sys, base64
from depth_estimation import PostcardMaker
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
st.markdown("<style>body {margin:0; overflow:hidden; background-color:#f5e6d2;}</style>", unsafe_allow_html=True)

st.markdown("""
<h1 style="font-family:'Press Start 2P', cursive; text-align:center; color:#a0522d; margin-top:20px;">
DigiCard
</h1>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

user_text = st.text_input("Add a message to your postcard:", key="msg_input")

stickers = {
    "Heart": "https://images.vexels.com/media/users/3/158488/isolated/preview/a086f6de9db88086d4268015294fcd9a-cool-sticker.png",
}
selected_sticker = st.selectbox("Add a sticker:", ["None"] + list(stickers.keys()))

uploaded_file = st.file_uploader("Upload an image", type=["png","jpg","jpeg"], key="file_uploader")

if uploaded_file:
    loading = st.empty()
    loading.markdown("<h3 style='text-align:center;'>Processing your 3D scrapbook...</h3>", unsafe_allow_html=True)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        package = pmaker.convert_image(image_path=tmp_path)

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
                        border-radius:12px;
                        z-index:{i+1}; transition: transform 0.2s; transform: scale({scale});">
            '''

        text_html = ""
        if user_text:
            text_html = f'''
            <div id="user-text" style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);
                        color:#333; font-size:2em; font-family:'Patrick Hand', cursive;
                        text-align:center; z-index:100; cursor:move;">
                {user_text}
            </div>
            '''

        sticker_html = ""
        if selected_sticker != "None":
            sticker_url = stickers[selected_sticker]
            sticker_html = f'''
            <img id="sticker" src="{sticker_url}" style="position:absolute; top:20px; right:20px; width:80px; height:80px; z-index:101; cursor:move;">
            '''

        html_code = f"""
        <link href="https://fonts.googleapis.com/css2?family=Patrick+Hand&display=swap" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/interactjs/dist/interact.min.js"></script>

        <div class="parallax-container" style="position:fixed; top:0; left:0; width:100vw; height:100vh;
             display:flex; justify-content:center; align-items:center;">
            <!-- Full-screen card -->
            <div id="card" style="position:relative; width:90vw; height:90vh; background:white; 
                 border-radius:12px; box-shadow:0 8px 24px rgba(0,0,0,0.25); overflow:hidden;">
                 
                <img src="data:image/png;base64,{original_b64}" style="width:100%; height:100%; object-fit:cover; border-radius:12px; position:absolute; top:0; left:0; z-index:0;">
                {html_layers}
                {text_html}
                {sticker_html}
            </div>

            <button id="motion-btn" style="position:absolute; bottom:20px; left:20px; z-index:1000; padding:10px 15px; font-size:16px;">
                Enable Motion
            </button>
        </div>

        <script>
        const card = document.getElementById('card');
        const layers = document.querySelectorAll('.layer');
        const maxTranslate = 15;

        // Gyro effect
        const handleMotion = (event) => {{
            const gyroX  = event.gamma || 0;
            const gyroY  = event.beta || 0;
            layers.forEach((layer, i) => {{
                const depth = (i + 1) / layers.length;
                let tx = gyroX  * depth;
                let ty = gyroY  * depth;

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

        // --- Interactable drag for text and sticker ---
        interact('#user-text').draggable({{
            modifiers: [
                interact.modifiers.restrictRect({{ restriction: 'parent' }})
            ],
            inertia: true,
            listeners: {{
                move (event) {{
                    const target = event.target;
                    const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
                    const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
                    target.style.transform = `translate(${x}px, ${y}px)`;
                    target.setAttribute('data-x', x);
                    target.setAttribute('data-y', y);
                }}
            }}
        }});

        interact('#sticker').draggable({{
            modifiers: [
                interact.modifiers.restrictRect({{ restriction: 'parent' }})
            ],
            inertia: true,
            listeners: {{
                move (event) {{
                    const target = event.target;
                    const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
                    const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
                    target.style.transform = `translate(${x}px, ${y}px)`;
                    target.setAttribute('data-x', x);
                    target.setAttribute('data-y', y);
                }}
            }}
        }});
        </script>
        """

        components.html(html_code, height=800)

    finally:
        os.unlink(tmp_path)
