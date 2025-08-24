import React, { useState } from "react";
import axios from "axios";

function App() {
  const [url, setUrl] = useState("");
  const [resolution, setResolution] = useState("1080p");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      // Send JSON instead of FormData
      const response = await axios.post("https://creator-dock-update.onrender.com/", {
        url: url,
        resolution: resolution
      }, {
        headers: { 
          "Content-Type": "application/json" 
        },
        timeout: 120000 // 2 minutes timeout for video processing
      });

      setMessage(response.data?.message || "Video downloaded successfully!");
      
      // If there's a download URL, you can handle it here
      if (response.data?.download_url) {
        // Option: Open download link
        window.open(`https://creator-dock-update.onrender.com${response.data.download_url}`, '_blank');
      }
      
    } catch (error) {
      console.error("Error details:", error.response?.data);
      
      if (error.response?.data?.message) {
        setMessage(`Error: ${error.response.data.message}`);
      } else if (error.code === 'ECONNABORTED') {
        setMessage("Request timed out. Video might be too large or processing is taking too long.");
      } else {
        setMessage("Error downloading video. Check URL and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "500px", margin: "50px auto", fontFamily: "Arial, sans-serif" }}>
      <h1>Video Downloader</h1>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "15px" }}>
          <label htmlFor="url">YouTube URL:</label>
          <input
            type="url"
            id="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            placeholder="https://www.youtube.com/watch?v=..."
            style={{ width: "100%", padding: "8px", marginTop: "5px" }}
          />
        </div>

        <div style={{ marginBottom: "15px" }}>
          <label htmlFor="resolution">Resolution:</label>
          <select
            id="resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            style={{ width: "100%", padding: "8px", marginTop: "5px" }}
          >
            <option value="144p">144p</option>
            <option value="240p">240p</option>
            <option value="360p">360p</option>
            <option value="480p">480p</option>
            <option value="720p">720p</option>
            <option value="1080p">1080p</option>
          </select>
        </div>

        <button 
          type="submit" 
          disabled={loading}
          style={{ 
            padding: "10px 20px", 
            cursor: loading ? "not-allowed" : "pointer",
            backgroundColor: loading ? "#ccc" : "#007bff",
            color: "white",
            border: "none",
            borderRadius: "4px"
          }}
        >
          {loading ? "Processing..." : "Download"}
        </button>
      </form>

      {message && (
        <p style={{ 
          marginTop: "20px", 
          fontWeight: "bold",
          color: message.includes("Error") ? "red" : "green"
        }}>
          {message}
        </p>
      )}
      
      {loading && (
        <p style={{ marginTop: "10px", color: "#666" }}>
          Please wait, this may take a few minutes depending on video size...
        </p>
      )}
    </div>
  );
}

export default App;