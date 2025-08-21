from flask import Flask, request, jsonify, send_from_directory
from pytubefix import YouTube
import os
import subprocess
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from React frontend

# Folder to save downloaded videos
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["POST"])
def download_video():
    try:
        url = request.form.get("url")
        resolution = request.form.get("resolution") or "1080p"

        yt = YouTube(url)

        # Try progressive stream first (video + audio in one)
        video_stream = yt.streams.filter(res=resolution, progressive=True).first()

        if video_stream:
            output_path = video_stream.download(
                output_path=DOWNLOAD_FOLDER, filename=f"video_{resolution}.mp4"
            )
            message = "Downloaded video with audio successfully."
        else:
            # High-res video-only + audio
            video_stream = yt.streams.filter(
                res=resolution, file_extension="mp4", only_video=True
            ).first()
            audio_stream = yt.streams.filter(
                only_audio=True, file_extension="mp4"
            ).order_by('abr').desc().first()

            if not video_stream or not audio_stream:
                return jsonify({"message": "Requested resolution not available."}), 400

            video_path = video_stream.download(
                output_path=DOWNLOAD_FOLDER, filename="video.mp4"
            )
            audio_path = audio_stream.download(
                output_path=DOWNLOAD_FOLDER, filename="audio.mp4"
            )

            output_path = os.path.join(DOWNLOAD_FOLDER, f"output_{resolution}.mp4")

            # Merge using FFmpeg
            subprocess.run([
                "ffmpeg",
                "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                output_path
            ], check=True)

            # Cleanup temporary files
            os.remove(video_path)
            os.remove(audio_path)

            message = "Downloaded and merged video successfully."

        # Return JSON with video path for frontend
        filename = os.path.basename(output_path)
        return jsonify({
            "message": message,
            "download_url": f"/download/{filename}"
        })

    except Exception as e:
        return jsonify({"message": f"Error: {e}"}), 500


# Route to serve downloaded files
@app.route("/download/<filename>")
def serve_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
