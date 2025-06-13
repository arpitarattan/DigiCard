import cv2
import os
import shutil
from pathlib import Path
import pycolmap, subprocess
from pycolmap import Database, Reconstruction

def extract_frames(video_path, output_dir, every_n=5):
    '''
    Function to extract frames every_n times from a video and save images
    '''
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path) 
    frame_idx = 0
    saved = []

    while True:
        ret, frame = cap.read()
        if not ret: break # Return when no more frames to process
        if frame_idx % every_n == 0:
            path = os.path.join(output_dir, f"frame_{frame_idx}.jpg")
            cv2.imwrite(path, frame)
            saved.append(path)
        frame_idx += 1
    return saved

def save_sparse_points_to_ply(reconstruction: pycolmap.Reconstruction, output_path: str):
    """Write sparse point cloud from COLMAP reconstruction to PLY format."""
    with open(output_path, 'w') as f:
        points = reconstruction.points3D
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        f.write("end_header\n")
        for pt in points.values():
            x, y, z = pt.xyz
            r, g, b = pt.color
            f.write(f"{x} {y} {z} {r} {g} {b}\n")  

def run_sparse_reconstruction(image_dir, work_dir):
    '''
    Function: Run COLMAP to get features from all frames
    Input: image_dir - directory with all frames
           work_dir - directory to store pointcloud database
    Return: ply_path - path to point cloud
    '''
    work_dir = Path(work_dir)
    db_path = work_dir / "database.db"
    sparse_dir = work_dir / "sparse"

    if db_path.exists(): db_path.unlink() # Recreate db each time

    # Extract features from each frame (using SIFT)
    pycolmap.extract_features(
        database_path=str(db_path),
        image_path=str(image_dir),
        camera_model='SIMPLE_RADIAL',
    )

    pycolmap.match_exhaustive(str(db_path)) # Match points 

    sparse_dir.mkdir(parents=True, exist_ok=True)
    
    # Recover 3D points by estimating camera posing (i.e. create point cloud)
    reconstruction = pycolmap.incremental_mapping(
        database_path=str(db_path),
        image_path=str(image_dir),
        output_path=str(sparse_dir)
    )

    # Save the sparse point cloud
    if reconstruction:
        model = list(reconstruction.values())[0]
        model.write(str(sparse_dir))
        ply_path = sparse_dir / "points3D.ply"
        save_sparse_points_to_ply(model, str(ply_path)) # Convert point cloud binary to .ply for future use
        return str(ply_path)
    else:
        raise Exception("No reconstruction generated.")

def run_dense_reconstruction(image_dir, sparse_dir, output_dir):
    # Step 1: Undistort images
    subprocess.run([
        "colmap", "image_undistorter",
        "--image_path", str(image_dir),
        "--input_path", str(sparse_dir),
        "--output_path", str(output_dir),
        "--output_type", "COLMAP"
    ], check=True)

    # Step 2: PatchMatch stereo
    subprocess.run([
        "colmap", "patch_match_stereo",
        "--workspace_path", str(output_dir),
        "--workspace_format", "COLMAP",
        "--PatchMatchStereo.geom_consistency", "true"
    ], check=True)

    # Step 3: Stereo fusion
    subprocess.run([
        "colmap", "stereo_fusion",
        "--workspace_path", str(output_dir),
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", str(Path(output_dir) / "fused.ply")
    ], check=True)

    return Path(output_dir) / "fused.ply"

def process_video_to_pointcloud(video_path, output_dir="pycolmap_output"):
    frame_dir = Path(output_dir) / "frames"
    #extract_frames(video_path, str(frame_dir))
    # 1. Run sparse SfM via pycolmap
    #sparse_dir = run_sparse_reconstruction(frame_dir, output_dir)

    # 2. Run dense point cloud fusion via colmap CLI
    ply_path = run_dense_reconstruction(frame_dir, 'pycolmap_output/sparse/points3D.points3D.ply', "pycolmap_output/dense")

    return ply_path

if __name__ == "__main__":
    ply_file = process_video_to_pointcloud("inputs/test.mov") # Process video and return point cloud
    print(f'Successfully created pointcloud to {ply_file}')

    