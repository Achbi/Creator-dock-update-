import cv2
import subprocess
import os

# Paths
input_path = "output_1080p.mp4"       # Original video
temp_video_path = "temp_4k_video.mp4" # Upscaled video without audio
output_path = "output_4k_final.mp4"   # Final 4K video with audio

# Create VideoCapture object
cap = cv2.VideoCapture(input_path)

# Video properties
fps = int(cap.get(cv2.CAP_PROP_FPS))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# 4K resolution
fourk_width = 3840
fourk_height = 2160

# Define codec and VideoWriter
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(temp_video_path, fourcc, fps, (fourk_width, fourk_height))

frame_number = 0

print("Upscaling video to 4K...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Resize frame to 4K
    upscaled_frame = cv2.resize(frame, (fourk_width, fourk_height), interpolation=cv2.INTER_CUBIC)
    out.write(upscaled_frame)

    # Progress
    frame_number += 1
    progress = (frame_number / total_frames) * 100
    print(f"Progress: {progress:.2f}%", end="\r")

cap.release()
out.release()
print("\nVideo upscaled to 4K (without audio).")

# Merge audio using FFmpeg
print("Merging original audio...")
command = [
    "ffmpeg",
    "-i", temp_video_path,
    "-i", input_path,
    "-c:v", "copy",   # keep upscaled video as-is
    "-c:a", "aac",    # encode audio to aac
    "-map", "0:v:0",  # video from first input
    "-map", "1:a:0",  # audio from second input
    "-y",             # overwrite output if exists
    output_path
]

subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
print(f"Final 4K video with audio saved as '{output_path}'.")

# Optional: remove temp video
if os.path.exists(temp_video_path):
    os.remove(temp_video_path)
