from flask import Flask, request, jsonify, send_from_directory
from pytubefix import YouTube
import os
import subprocess
from flask_cors import CORS
import time
import random
import logging
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Download folder (must be writable in Render)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def clean_filename(title, max_length=50):
    """Clean and truncate filename to avoid filesystem issues"""
    if not title:
        return "video"
    # Remove special characters and limit length
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    return safe_title[:max_length] if safe_title else "video"

def get_youtube_object(url, max_retries=3):
    """Get YouTube object with multiple fallback methods to bypass bot detection"""
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # Exponential backoff with jitter
                delay = random.uniform(3, 8) * (2 ** attempt)
                logger.info(f"Waiting {delay:.1f}s before retry {attempt+1}")
                time.sleep(delay)
            
            logger.info(f"Attempt {attempt+1}: Trying to access YouTube video")
            
            # Try different approaches with additional options
            if attempt == 0:
                logger.info("Using po_token + WEB client approach")
                return YouTube(url, use_po_token=True, client='WEB')
            elif attempt == 1:
                logger.info("Using WEB client only")
                return YouTube(url, client='WEB')
            else:
                logger.info("Using default approach with delay")
                time.sleep(random.uniform(1, 3))  # Extra delay for last attempt
                return YouTube(url)
                
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            
            # If we get a rate limit error, wait longer
            if any(keyword in error_str for keyword in ["429", "too many", "rate limit", "bot"]):
                if attempt < max_retries - 1:
                    wait_time = random.uniform(10, 20)
                    logger.info(f"Rate limited, waiting {wait_time:.1f}s before next attempt")
                    time.sleep(wait_time)
            
            if attempt == max_retries - 1:
                raise e
            continue
    
    return None

def cleanup_old_files(max_age_hours=1):
    """Clean up files older than specified hours to save disk space"""
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
    """API information and health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "YouTube Video Downloader API",
        "message": "Service is running successfully",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "download": "POST / - Download YouTube video",
            "file": "GET /download/<filename> - Download file",
            "health": "GET /health - Health check"
        },
        "usage": {
            "method": "POST",
            "url": "/",
            "body": {
                "url": "YouTube video URL",
                "resolution": "Video resolution (e.g., 1080p, 720p)"
            }
        }
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Detailed health check with system information"""
    try:
        # Check disk space
        stat = os.statvfs(DOWNLOAD_FOLDER)
        free_space_mb = (stat.f_bavail * stat.f_frsize) / (1024*1024)
        
        # Count files in download folder
        file_count = len([f for f in os.listdir(DOWNLOAD_FOLDER) if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f))])
        
        return jsonify({
            "status": "healthy",
            "download_folder_exists": os.path.exists(DOWNLOAD_FOLDER),
            "free_disk_space_mb": round(free_space_mb, 2),
            "files_in_download_folder": file_count,
            "timestamp": datetime.now().isoformat(),
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/", methods=["POST"])
def download_video():
    """Main video download endpoint with comprehensive error handling"""
    start_time = time.time()
    
    try:
        # Clean up old files to free space
        cleanup_old_files()
        
        # Parse and validate request data
        data = request.json
        if not data:
            return jsonify({"message": "No JSON data provided. Send JSON with 'url' and optional 'resolution' fields."}), 400
            
        url = data.get("url", "").strip()
        resolution = data.get("resolution", "1080p").strip()

        if not url:
            return jsonify({"message": "No URL provided in request body"}), 400

        # Validate YouTube URL format
        valid_domains = [
            "https://www.youtube.com/watch",
            "https://youtu.be/",
            "https://m.youtube.com/watch",
            "https://youtube.com/watch"
        ]
        
        if not any(url.startswith(domain) for domain in valid_domains):
            return jsonify({
                "message": "Please provide a valid YouTube URL (youtube.com or youtu.be)"
            }), 400

        logger.info(f"Processing request - URL: {url[:60]}{'...' if len(url) > 60 else ''}, Resolution: {resolution}")

        # Add initial random delay to avoid rate limiting (longer delay)
        initial_delay = random.uniform(3, 8)
        logger.info(f"Initial delay: {initial_delay:.1f}s")
        time.sleep(initial_delay)

        # Get YouTube object with multiple retry strategies
        yt = get_youtube_object(url)
        
        if not yt:
            return jsonify({
                "message": "Could not access video. It might be private, region-blocked, age-restricted, or temporarily unavailable."
            }), 429

        # Extract video information
        try:
            title = yt.title or "Unknown Video"
            duration = yt.length or 0
            view_count = getattr(yt, 'views', 0)
        except Exception as e:
            logger.warning(f"Could not extract all video metadata: {e}")
            title = "Unknown Video"
            duration = 0
            view_count = 0
        
        safe_title = clean_filename(title)
        logger.info(f"Video found: '{title}' (Duration: {duration}s)")

        # Try progressive stream first (single file with video + audio)
        logger.info(f"Searching for progressive stream at {resolution}")
        video_stream = yt.streams.filter(res=resolution, progressive=True).first()

        if video_stream:
            logger.info(f"Found progressive stream at {resolution}")
            timestamp = int(time.time())
            filename = f"{safe_title}_{resolution}_{timestamp}.mp4"
            
            try:
                output_path = video_stream.download(
                    output_path=DOWNLOAD_FOLDER,
                    filename=filename
                )
                message = f"Downloaded '{title}' at {resolution} successfully."
            except Exception as e:
                logger.error(f"Progressive download failed: {e}")
                return jsonify({
                    "message": f"Download failed: {str(e)[:200]}"
                }), 500
            
        else:
            logger.info(f"No progressive stream at {resolution}, trying separate video+audio streams")
            
            # Get separate video and audio streams
            video_stream = yt.streams.filter(
                res=resolution, 
                file_extension="mp4", 
                only_video=True
            ).first()
            
            # Fallback to best available resolution if exact resolution not found
            if not video_stream:
                logger.info("Exact resolution not available, getting best quality video stream")
                video_stream = yt.streams.filter(
                    file_extension="mp4", 
                    only_video=True
                ).order_by('resolution').desc().first()
                
            # Get best quality audio stream
            audio_stream = yt.streams.filter(
                only_audio=True, 
                file_extension="mp4"
            ).order_by('abr').desc().first()

            # Try alternative audio formats if mp4 audio not available
            if not audio_stream:
                logger.info("MP4 audio not found, trying other formats")
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()

            if not video_stream or not audio_stream:
                available_resolutions = [s.resolution for s in yt.streams.filter(progressive=True) if s.resolution]
                return jsonify({
                    "message": f"No suitable streams found for {resolution}. Available resolutions: {', '.join(set(available_resolutions)) if available_resolutions else 'None'}"
                }), 400

            logger.info(f"Downloading video stream: {video_stream.resolution}@{video_stream.fps}fps")
            logger.info(f"Downloading audio stream: {audio_stream.abr}")
            
            # Create unique temporary filenames
            timestamp = int(time.time())
            video_temp = f"video_temp_{timestamp}.mp4"
            audio_temp = f"audio_temp_{timestamp}.mp4"
            
            try:
                # Download video stream
                video_path = video_stream.download(
                    output_path=DOWNLOAD_FOLDER, 
                    filename=video_temp
                )
                
                # Download audio stream
                audio_path = audio_stream.download(
                    output_path=DOWNLOAD_FOLDER, 
                    filename=audio_temp
                )
                
            except Exception as e:
                logger.error(f"Stream download failed: {e}")
                # Cleanup any partial downloads
                for temp_file in [f"{DOWNLOAD_FOLDER}/{video_temp}", f"{DOWNLOAD_FOLDER}/{audio_temp}"]:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass
                return jsonify({
                    "message": f"Failed to download video streams: {str(e)[:200]}"
                }), 500

            # Final output filename
            filename = f"{safe_title}_{resolution}_{timestamp}.mp4"
            output_path = os.path.join(DOWNLOAD_FOLDER, filename)

            logger.info("Merging video and audio streams with FFmpeg...")
            
            # FFmpeg command with robust settings
            ffmpeg_cmd = [
                "ffmpeg", "-y",  # Overwrite output file
                "-i", video_path,  # Video input
                "-i", audio_path,  # Audio input
                "-c:v", "copy",    # Copy video codec (no re-encoding)
                "-c:a", "aac",     # Convert audio to AAC
                "-avoid_negative_ts", "make_zero",  # Fix timestamp issues
                "-movflags", "faststart",  # Optimize for web streaming
                "-shortest",       # End when shortest input ends
                "-loglevel", "error",  # Reduce FFmpeg verbosity
                output_path
            ]
            
            try:
                result = subprocess.run(
                    ffmpeg_cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=600,  # 10 minute timeout
                    cwd=DOWNLOAD_FOLDER
                )
                
                if result.returncode != 0:
                    logger.error(f"FFmpeg failed with code {result.returncode}: {result.stderr}")
                    raise subprocess.CalledProcessError(result.returncode, ffmpeg_cmd, result.stderr)
                    
                logger.info("FFmpeg merge completed successfully")
                
            except subprocess.TimeoutExpired:
                logger.error("FFmpeg timeout - video too long or complex")
                return jsonify({
                    "message": "Video processing timed out. The video might be too long or in a complex format."
                }), 408
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg processing failed: {e}")
                return jsonify({
                    "message": "Video processing failed. The video format might not be supported."
                }), 500
            finally:
                # Clean up temporary files
                for temp_file in [video_path, audio_path]:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                            logger.info(f"Cleaned up temp file: {os.path.basename(temp_file)}")
                    except Exception as e:
                        logger.warning(f"Could not remove temp file {temp_file}: {e}")
                        
            actual_resolution = video_stream.resolution or "unknown"
            message = f"Downloaded '{title}' at {actual_resolution} and merged successfully."

        # Verify final file exists and get information
        if not os.path.exists(output_path):
            return jsonify({"message": "Download completed but output file not found"}), 500
            
        try:
            file_size = os.path.getsize(output_path) / (1024*1024)  # Size in MB
        except:
            file_size = 0
            
        processing_time = round(time.time() - start_time, 2)
        
        logger.info(f"Download completed successfully in {processing_time}s, file size: {file_size:.1f}MB")
        
        # Return success response
        return jsonify({
            "message": message,
            "download_url": f"/download/{os.path.basename(output_path)}",
            "title": title,
            "duration": f"{duration} seconds" if duration else "Unknown",
            "file_size": f"{file_size:.1f} MB",
            "processing_time": f"{processing_time} seconds",
            "resolution": resolution,
            "views": view_count if view_count else None
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "message": "Video processing timed out. The video might be too long or complex to process."
        }), 408
        
    except Exception as e:
        error_msg = str(e)
        processing_time = round(time.time() - start_time, 2)
        
        logger.error(f"Error after {processing_time}s: {error_msg}")
        
        # Categorize and handle different types of errors
        if any(keyword in error_msg.lower() for keyword in ["bot", "blocked", "403", "forbidden", "429", "too many requests"]):
            return jsonify({
                "message": "Access temporarily blocked by YouTube. Please try again in a few minutes.",
                "error_type": "rate_limited"
            }), 429
            
        elif any(keyword in error_msg.lower() for keyword in ["private", "unavailable", "deleted", "removed"]):
            return jsonify({
                "message": "This video is private, unavailable, or has been removed.",
                "error_type": "video_unavailable"
            }), 400
            
        elif "timeout" in error_msg.lower():
            return jsonify({
                "message": "Request timed out. The video might be too large or processing is taking too long.",
                "error_type": "timeout"
            }), 408
            
        elif any(keyword in error_msg.lower() for keyword in ["network", "connection", "resolve"]):
            return jsonify({
                "message": "Network error occurred. Please check your connection and try again.",
                "error_type": "network_error"
            }), 503
            
        elif "age" in error_msg.lower() and "restricted" in error_msg.lower():
            return jsonify({
                "message": "This video is age-restricted and cannot be downloaded.",
                "error_type": "age_restricted"
            }), 400
            
        else:
            # Generic error with truncated message to avoid exposing sensitive info
            return jsonify({
                "message": f"An unexpected error occurred: {error_msg[:200]}{'...' if len(error_msg) > 200 else ''}",
                "error_type": "unknown"
            }), 500

@app.route("/download/<filename>", methods=["GET"])
def serve_file(filename):
    """Serve downloaded files with proper error handling"""
    try:
        # Sanitize filename to prevent directory traversal attacks
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"message": "Invalid filename"}), 400
            
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            return jsonify({
                "message": "File not found. It may have been cleaned up due to storage limits."
            }), 404
            
        # Check file size before serving
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return jsonify({"message": "File is empty or corrupted"}), 500
            
        logger.info(f"Serving file: {filename} ({file_size / (1024*1024):.1f} MB)")
        
        return send_from_directory(
            DOWNLOAD_FOLDER, 
            filename, 
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )
        
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return jsonify({"message": "Error accessing file"}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "message": "Endpoint not found",
        "available_endpoints": {
            "GET /": "API information",
            "POST /": "Download video", 
            "GET /health": "Health check",
            "GET /download/<filename>": "Download file"
        }
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle method not allowed errors"""
    return jsonify({
        "message": "Method not allowed for this endpoint",
        "hint": "Use POST method for video downloads"
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "message": "Internal server error occurred",
        "timestamp": datetime.now().isoformat()
    }), 500

# Initialize app
if __name__ == "__main__":
    # Get port from environment variable (important for Render)
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    logger.info(f"Starting YouTube Downloader API on port {port}")
    logger.info(f"Debug mode: {debug_mode}")
    logger.info(f"Download folder: {os.path.abspath(DOWNLOAD_FOLDER)}")
    
    # Run the Flask app
    app.run(
        host="0.0.0.0", 
        port=port, 
        debug=debug_mode,
        threaded=True
    )