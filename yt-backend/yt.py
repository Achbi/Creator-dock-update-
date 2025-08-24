from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import time
import random
import logging
from datetime import datetime
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Download folder
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def clean_filename(title, max_length=50):
    """Clean and truncate filename"""
    if not title:
        return "video"
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    return safe_title[:max_length] if safe_title else "video"

def cleanup_old_files(max_age_hours=1):
    """Clean up old files to save space"""
    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        
        for filename in os.listdir(DOWNLOAD_FOLDER):
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                        logger.info(f"Cleaned up old file: {filename}")
                    except Exception as e:
                        logger.warning(f"Could not remove {filename}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old files")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

@app.route("/", methods=["GET"])
def home():
    """API information endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "YouTube Video Downloader API (yt-dlp)",
        "message": "Service is running successfully",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "download": "POST / - Download YouTube video",
            "file": "GET /download/<filename> - Download file",
            "health": "GET /health - Health check"
        }
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        stat = os.statvfs(DOWNLOAD_FOLDER)
        free_space_mb = (stat.f_bavail * stat.f_frsize) / (1024*1024)
        file_count = len([f for f in os.listdir(DOWNLOAD_FOLDER) if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f))])
        
        return jsonify({
            "status": "healthy",
            "download_folder_exists": os.path.exists(DOWNLOAD_FOLDER),
            "free_disk_space_mb": round(free_space_mb, 2),
            "files_in_download_folder": file_count,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/", methods=["POST"])
def download_video():
    """Main video download endpoint using yt-dlp"""
    start_time = time.time()
    
    try:
        cleanup_old_files()
        
        # Parse request
        data = request.json
        if not data:
            return jsonify({"message": "No JSON data provided"}), 400
            
        url = data.get("url", "").strip()
        resolution = data.get("resolution", "1080p").strip()

        if not url:
            return jsonify({"message": "No URL provided"}), 400

        # Validate YouTube URL
        valid_domains = [
            "https://www.youtube.com/watch",
            "https://youtu.be/",
            "https://m.youtube.com/watch",
            "https://youtube.com/watch"
        ]
        
        if not any(url.startswith(domain) for domain in valid_domains):
            return jsonify({
                "message": "Please provide a valid YouTube URL"
            }), 400

        logger.info(f"Processing: {url[:60]}... at {resolution}")

        # Add delay to avoid rate limiting
        delay = random.uniform(2, 5)
        logger.info(f"Initial delay: {delay:.1f}s")
        time.sleep(delay)

        # Convert resolution for yt-dlp
        height = resolution.replace('p', '')
        timestamp = int(time.time())
        
        # yt-dlp options with anti-bot measures
        ydl_opts = {
            'format': f'best[height<={height}]/best',
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{timestamp}.%(ext)s'),
            'restrictfilenames': True,
            'no_warnings': False,
            'extractaudio': False,
            'audioformat': 'mp3',
            'embed_thumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            # Anti-bot options
            'sleep_interval': random.randint(1, 3),
            'max_sleep_interval': 5,
            'sleep_interval_subtitles': 2,
            # Headers to appear more like a real browser
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip,deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Keep-Alive': '115',
                'Connection': 'keep-alive',
            }
        }

        downloaded_file = None
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extract info first
                logger.info("Extracting video information...")
                info = ydl.extract_info(url, download=False)
                
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                view_count = info.get('view_count', 0)
                
                logger.info(f"Video: '{title}' ({duration}s)")
                
                # Add another delay before downloading
                time.sleep(random.uniform(1, 3))
                
                # Download the video
                logger.info("Starting download...")
                ydl.download([url])
                
                # Find the downloaded file
                safe_title = clean_filename(title)
                
                # Look for files with the timestamp
                possible_files = []
                for f in os.listdir(DOWNLOAD_FOLDER):
                    if str(timestamp) in f and f.endswith(('.mp4', '.webm', '.mkv', '.avi')):
                        possible_files.append(f)
                
                if possible_files:
                    downloaded_file = possible_files[0]
                else:
                    # Fallback: get most recent file
                    files = [f for f in os.listdir(DOWNLOAD_FOLDER) 
                            if f.endswith(('.mp4', '.webm', '.mkv', '.avi'))]
                    if files:
                        files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_FOLDER, x)), reverse=True)
                        downloaded_file = files[0]

                if not downloaded_file:
                    return jsonify({"message": "Download completed but file not found"}), 500

                file_path = os.path.join(DOWNLOAD_FOLDER, downloaded_file)
                file_size = os.path.getsize(file_path) / (1024*1024)
                processing_time = round(time.time() - start_time, 2)
                
                logger.info(f"Download completed in {processing_time}s, file size: {file_size:.1f}MB")

                return jsonify({
                    "message": f"Downloaded '{title}' successfully!",
                    "download_url": f"/download/{downloaded_file}",
                    "title": title,
                    "duration": f"{duration} seconds" if duration else "Unknown",
                    "file_size": f"{file_size:.1f} MB",
                    "processing_time": f"{processing_time} seconds",
                    "views": view_count if view_count else None
                })

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"yt-dlp download error: {error_msg}")
                
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    return jsonify({
                        "message": "Too many requests. Please wait 5-10 minutes before trying again.",
                        "error_type": "rate_limited"
                    }), 429
                elif "Private video" in error_msg:
                    return jsonify({
                        "message": "This video is private and cannot be downloaded.",
                        "error_type": "private_video"
                    }), 400
                elif "Video unavailable" in error_msg:
                    return jsonify({
                        "message": "Video is unavailable or has been removed.",
                        "error_type": "unavailable"
                    }), 400
                elif "Sign in to confirm your age" in error_msg:
                    return jsonify({
                        "message": "This video is age-restricted and cannot be downloaded.",
                        "error_type": "age_restricted"
                    }), 400
                else:
                    return jsonify({
                        "message": f"Download failed: {error_msg[:200]}",
                        "error_type": "download_error"
                    }), 400

    except Exception as e:
        error_msg = str(e)
        processing_time = round(time.time() - start_time, 2)
        logger.error(f"Unexpected error after {processing_time}s: {error_msg}")
        
        return jsonify({
            "message": f"An unexpected error occurred: {error_msg[:200]}",
            "error_type": "unknown"
        }), 500

@app.route("/download/<filename>", methods=["GET"])
def serve_file(filename):
    """Serve downloaded files"""
    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"message": "Invalid filename"}), 400
            
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            return jsonify({"message": "File not found"}), 404
            
        return send_from_directory(
            DOWNLOAD_FOLDER, 
            filename, 
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return jsonify({"message": "Error accessing file"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "message": "Endpoint not found",
        "available_endpoints": ["GET /", "POST /", "GET /health", "GET /download/<filename>"]
    }), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    logger.info(f"Starting yt-dlp YouTube Downloader API on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)