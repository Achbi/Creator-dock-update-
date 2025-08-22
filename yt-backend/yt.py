from flask import Flask, request, jsonify, send_from_directory
from pytubefix import YouTube
import os
import subprocess
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Download folder (must be writable in Render)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route("/", methods=["POST"])
def download_video():
    try:
        # Use JSON request for better compatibility
        data = request.json
        url = data.get("url")
        resolution = data.get("resolution", "1080p")

        if not url:
            return jsonify({"message": "No URL provided"}), 400

        yt = YouTube(url)

        # Progressive stream (video + audio together)
        video_stream = yt.streams.filter(res=resolution, progressive=True).first()

        if video_stream:
            output_path = video_stream.download(
                output_path=DOWNLOAD_FOLDER,
                filename=f"video_{resolution}.mp4"
            )
            message = "Downloaded video with audio successfully."
        else:
            # Separate video and audio streams
            video_stream = yt.streams.filter(
                res=resolution, file_extension="mp4", only_video=True
            ).first()
            audio_stream = yt.streams.filter(
                only_audio=True, file_extension="mp4"
            ).order_by('abr').desc().first()

            if not video_stream or not audio_stream:
                return jsonify({"message": "Requested resolution not available."}), 400

            video_path = video_stream.download(
                output_path=DOWNLOAD_FOLDER, filename="video_temp.mp4"
            )
            audio_path = audio_stream.download(
                output_path=DOWNLOAD_FOLDER, filename="audio_temp.mp4"
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

            os.remove(video_path)
            os.remove(audio_path)
            message = "Downloaded and merged video successfully."

        filename = os.path.basename(output_path)
        return jsonify({
            "message": message,
            "download_url": f"/download/{filename}"
        })

    except Exception as e:
        return jsonify({"message": f"Error: {e}"}), 500


@app.route("/download/<filename>")
def serve_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


if __name__ == "__main__":
    # Important for Render: listen on 0.0.0.0 and port from environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
