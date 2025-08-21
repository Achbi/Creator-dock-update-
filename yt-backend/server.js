const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');
const { promisify } = require('util');

const app = express();
const port = process.env.PORT || 3000;
const execAsync = promisify(exec);

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Create downloads directory if it doesn't exist
const downloadsDir = path.join(__dirname, 'downloads');
if (!fs.existsSync(downloadsDir)) {
    fs.mkdirSync(downloadsDir, { recursive: true });
}

// Clean up old files (older than 1 hour)
const cleanupOldFiles = () => {
    fs.readdir(downloadsDir, (err, files) => {
        if (err) return;
        
        files.forEach(file => {
            const filePath = path.join(downloadsDir, file);
            fs.stat(filePath, (err, stats) => {
                if (err) return;
                
                const oneHourAgo = Date.now() - (60 * 60 * 1000);
                if (stats.mtime.getTime() < oneHourAgo) {
                    fs.unlink(filePath, (err) => {
                        if (err) console.error('Error deleting file:', err);
                    });
                }
            });
        });
    });
};

// Clean up every 30 minutes
setInterval(cleanupOldFiles, 30 * 60 * 1000);

// Helper function to check if yt-dlp is installed
const checkYtDlp = async () => {
    try {
        await execAsync('yt-dlp --version');
        return true;
    } catch (error) {
        try {
            await execAsync('youtube-dl --version');
            return 'youtube-dl';
        } catch (error2) {
            return false;
        }
    }
};

// Extract video ID from YouTube URL
const extractVideoId = (url) => {
    const regex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/;
    const match = url.match(regex);
    return match ? match[1] : null;
};

// Get video information
app.post('/api/video-info', async (req, res) => {
    try {
        const { url } = req.body;
        
        if (!url) {
            return res.status(400).json({ error: 'URL is required' });
        }

        const videoId = extractVideoId(url);
        if (!videoId) {
            return res.status(400).json({ error: 'Invalid YouTube URL' });
        }

        const ytDlpAvailable = await checkYtDlp();
        if (!ytDlpAvailable) {
            return res.status(500).json({ 
                error: 'yt-dlp or youtube-dl is not installed. Please install it to use this service.' 
            });
        }

        const command = ytDlpAvailable === 'youtube-dl' ? 'youtube-dl' : 'yt-dlp';
        
        // Get video info
        const infoCommand = `${command} --dump-json "${url}"`;
        const { stdout } = await execAsync(infoCommand, { timeout: 30000 });
        
        const videoInfo = JSON.parse(stdout);
        
        // Get available formats
        const formatsCommand = `${command} -F "${url}"`;
        const { stdout: formatsOutput } = await execAsync(formatsCommand, { timeout: 30000 });
        
        // Parse available formats
        const availableFormats = [];
        const formatLines = formatsOutput.split('\n');
        
        for (const line of formatLines) {
            if (line.includes('mp4') || line.includes('webm') || line.includes('m4a')) {
                const parts = line.split(/\s+/);
                if (parts.length > 3 && parts[2]) {
                    const quality = parts[2];
                    const format = parts[1];
                    if (quality !== 'format') {
                        availableFormats.push({
                            formatId: parts[0],
                            ext: format,
                            quality: quality,
                            note: parts.slice(3).join(' ')
                        });
                    }
                }
            }
        }

        const responseData = {
            id: videoInfo.id,
            title: videoInfo.title || 'Unknown Title',
            thumbnail: videoInfo.thumbnail || `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`,
            duration: videoInfo.duration ? formatDuration(videoInfo.duration) : 'Unknown',
            uploader: videoInfo.uploader || 'Unknown',
            view_count: videoInfo.view_count || 0,
            upload_date: videoInfo.upload_date || 'Unknown',
            description: videoInfo.description || '',
            formats: availableFormats.slice(0, 10) // Limit to first 10 formats
        };

        res.json(responseData);
        
    } catch (error) {
        console.error('Error getting video info:', error);
        res.status(500).json({ 
            error: 'Failed to get video information. Please check the URL and try again.' 
        });
    }
});

// Download video
app.post('/api/download', async (req, res) => {
    try {
        const { url, quality, format = 'mp4' } = req.body;
        
        if (!url) {
            return res.status(400).json({ error: 'URL is required' });
        }

        const videoId = extractVideoId(url);
        if (!videoId) {
            return res.status(400).json({ error: 'Invalid YouTube URL' });
        }

        const ytDlpAvailable = await checkYtDlp();
        if (!ytDlpAvailable) {
            return res.status(500).json({ 
                error: 'yt-dlp or youtube-dl is not installed.' 
            });
        }

        const command = ytDlpAvailable === 'youtube-dl' ? 'youtube-dl' : 'yt-dlp';
        
        // Generate unique filename
        const timestamp = Date.now();
        const safeTitle = `video_${videoId}_${timestamp}`;
        const outputPath = path.join(downloadsDir, `${safeTitle}.%(ext)s`);
        
        let downloadCommand;
        
        if (quality === 'audio') {
            // Audio only download
            downloadCommand = `${command} -x --audio-format mp3 --audio-quality 192K -o "${outputPath}" "${url}"`;
        } else if (quality === 'highest') {
            // Best quality
            downloadCommand = `${command} -f "best[ext=mp4]/best" -o "${outputPath}" "${url}"`;
        } else {
            // Specific quality
            const height = quality.replace('p', '');
            downloadCommand = `${command} -f "best[height<=${height}][ext=mp4]/best[height<=${height}]" -o "${outputPath}" "${url}"`;
        }

        console.log('Executing command:', downloadCommand);
        
        // Execute download command with timeout
        await execAsync(downloadCommand, { timeout: 300000 }); // 5 minutes timeout
        
        // Find the downloaded file
        const files = fs.readdirSync(downloadsDir);
        const downloadedFile = files.find(file => file.includes(safeTitle));
        
        if (!downloadedFile) {
            throw new Error('Downloaded file not found');
        }

        const filePath = path.join(downloadsDir, downloadedFile);
        const stats = fs.statSync(filePath);
        
        res.json({
            success: true,
            filename: downloadedFile,
            size: stats.size,
            downloadUrl: `/api/file/${downloadedFile}`
        });
        
    } catch (error) {
        console.error('Download error:', error);
        res.status(500).json({ 
            error: 'Download failed. Please try again or choose a different quality.' 
        });
    }
});

// Serve downloaded files
app.get('/api/file/:filename', (req, res) => {
    try {
        const filename = req.params.filename;
        const filePath = path.join(downloadsDir, filename);
        
        if (!fs.existsSync(filePath)) {
            return res.status(404).json({ error: 'File not found' });
        }

        const stats = fs.statSync(filePath);
        
        // Set headers for download
        res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
        res.setHeader('Content-Length', stats.size);
        res.setHeader('Content-Type', 'application/octet-stream');
        
        // Stream the file
        const fileStream = fs.createReadStream(filePath);
        fileStream.pipe(res);
        
        // Delete file after download
        fileStream.on('end', () => {
            setTimeout(() => {
                fs.unlink(filePath, (err) => {
                    if (err) console.error('Error deleting file:', err);
                });
            }, 5000); // Delete after 5 seconds
        });
        
    } catch (error) {
        console.error('File serve error:', error);
        res.status(500).json({ error: 'Error serving file' });
    }
});

// Health check endpoint
app.get('/api/health', async (req, res) => {
    const ytDlpAvailable = await checkYtDlp();
    res.json({ 
        status: 'ok', 
        ytDlp: ytDlpAvailable,
        message: ytDlpAvailable ? 'Service ready' : 'yt-dlp/youtube-dl not installed'
    });
});

// Helper function to format duration
const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
};

// Error handling middleware
app.use((error, req, res, next) => {
    console.error('Unhandled error:', error);
    res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(port, () => {
    console.log(`YouTube Downloader Server running on port ${port}`);
    console.log(`Access the application at http://localhost:${port}`);
    
    // Check yt-dlp availability on startup
    checkYtDlp().then(available => {
        if (available) {
            console.log(`✅ ${available === 'youtube-dl' ? 'youtube-dl' : 'yt-dlp'} is available`);
        } else {
            console.log('❌ yt-dlp/youtube-dl is not installed. Please install it to use this service.');
            console.log('Install with: pip install yt-dlp');
        }
    });
});

module.exports = app;