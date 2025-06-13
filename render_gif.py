import numpy as np
import trimesh, pyrender, imageio, os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = "assets"

def compute_look_at_matrix(eye, target, up=[0, 1, 0]):
    eye = np.array(eye)
    target = np.array(target)
    up = np.array(up)

    forward = target - eye
    forward /= np.linalg.norm(forward)

    right = np.cross(up, forward)
    right /= np.linalg.norm(right)

    true_up = np.cross(forward, right)
    true_up /= np.linalg.norm(true_up)

    # Rotation matrix
    rotation = np.vstack([right, true_up, forward])
    rotation = np.transpose(rotation)

    # Translation
    translation = -rotation @ eye

    # Compose 4x4 matrix
    view_matrix = np.eye(4)
    view_matrix[:3, :3] = rotation
    view_matrix[:3, 3] = translation

    return view_matrix


def render_orbit_frames(ply_path, num_frames=36, image_size=(512, 512)):
    loaded = trimesh.load(ply_path)

    if isinstance(loaded, trimesh.points.PointCloud):
        points = loaded.vertices
        colors = loaded.colors if loaded.colors is not None else np.ones((len(points), 3)) * 255
        mesh_node = pyrender.Mesh.from_points(points, colors / 255.0)
        center = np.mean(points, axis=0)
        size = np.linalg.norm(np.max(points, axis=0) - np.min(points, axis=0))
    elif isinstance(loaded, trimesh.Trimesh):
        mesh_node = pyrender.Mesh.from_trimesh(loaded, smooth=False)
        center = loaded.bounding_box.centroid
        size = np.linalg.norm(loaded.bounding_box.extents)
    else:
        raise Exception(f"Unsupported type loaded from PLY: {type(loaded)}")

    camera_distance = size * 0.7
    scene = pyrender.Scene()
    scene.add(mesh_node)
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=2.0))

    frames = []

    for i in range(num_frames):
        angle = 2 * np.pi * (i / num_frames)
        cam_position = center + camera_distance * np.array([np.cos(angle), 0.1, np.sin(angle)])
        pose = compute_look_at_matrix(cam_position, center)

        camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
        cam_node = scene.add(camera, pose=pose)

        r = pyrender.OffscreenRenderer(*image_size)
        color, _ = r.render(scene)
        frame = Image.fromarray(color)
        frame.save(f'frames/frame_{i}.jpg')
        frames.append(frame)
        r.delete()

        scene.remove_node(cam_node)

    return frames


def make_postcard_front(frame: Image.Image, border=20):
    w, h = frame.size
    new_img = Image.new("RGB", (w + border * 2, h + border * 2), "white")
    new_img.paste(frame, (border, border))
    return new_img


def make_postcard_back(size=(552, 552), location="Unknown", message="Greetings from...", stamp_path=None):
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)

    # Optional font
    try:
        font = ImageFont.truetype(os.path.join(ASSETS_DIR, "handwriting_font.ttf"), 20)
    except:
        font = ImageFont.load_default()

    # Draw message
    draw.text((20, 20), f"{message} {location}!", fill="black", font=font)

    # Draw fake address lines
    for i in range(5):
        y = 100 + i * 25
        draw.line([(300, y), (size[0] - 20, y)], fill="gray", width=1)

    # Draw fake stamp
    if stamp_path and os.path.exists(stamp_path):
        stamp = Image.open(stamp_path).convert("RGBA")
        stamp = stamp.resize((100, 100))
        img.paste(stamp, (size[0] - 120, 20), stamp)

    return img


def stack_front_back_gif(front_frames, back_img, output_path="postcard.gif", fps=12):
    height = front_frames[0].height + back_img.height
    width = max(front_frames[0].width, back_img.width)

    final_frames = []
    for frame in front_frames:
        combined = Image.new("RGB", (width, height), "white")
        combined.paste(frame, (0, 0))
        combined.paste(back_img, (0, frame.height))
        final_frames.append(combined)

    final_frames[0].save(
        output_path, format="GIF", save_all=True,
        append_images=final_frames[1:], duration=int(1000/fps), loop=0
    )
    print(f"[✅] Final postcard saved as: {output_path}")


# 🏁 MAIN FUNCTION
if __name__ == "__main__":
    ply_path = "pycolmap_output/sparse/points3D.ply"
    location = "Tokyo"
    stamp_path = os.path.join(ASSETS_DIR, "stamp.png")

    # Step 1: Render orbiting frames
    orbit_frames = render_orbit_frames(ply_path)

    # # Step 2: Wrap each with a border
    front_postcard_frames = [make_postcard_front(f) for f in orbit_frames]

    # # Step 3: Build a single back image
    back_image = make_postcard_back(
        size=front_postcard_frames[0].size,
        location=location,
        message="Greetings from",
        stamp_path=stamp_path
    )

    # # Step 4: Stack and save
    stack_front_back_gif(front_postcard_frames, back_image, output_path="postcard_output.gif")
