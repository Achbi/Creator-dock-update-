import React, { useState } from "react";
import axios from "axios";

function App() {
  const [url, setUrl] = useState("");
  const [resolution, setResolution] = useState("1080p");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      // Send POST request to Flask backend
      const formData = new FormData();
      formData.append("url", url);
      formData.append("resolution", resolution);

const response = await axios.post(
  "https://creator-dock-update.onrender.com/",
  formData,
  {
    headers: { "Content-Type": "multipart/form-data" },
  }
);

      // Flask currently returns HTML, so you might want to return JSON from Flask
      setMessage(response.data?.message || "Video downloaded successfully!");
    } catch (error) {
      console.error(error);
      setMessage("Error downloading video. Check URL and try again.");
    }
  };

  return (
    <div style={{ maxWidth: "500px", margin: "50px auto", fontFamily: "Arial, sans-serif" }}>
      <h1>Video deployment</h1>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "15px" }}>
          <label htmlFor="url">YouTube URL:</label>
          <input
            type="text"
            id="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            style={{ width: "100%", padding: "8px", marginTop: "5px" }}
          />
        </div>

        <div style={{ marginBottom: "15px" }}>
          <label htmlFor="resolution">Resolution:</label>
          <input
            type="text"
            id="resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            placeholder="1080p"
            style={{ width: "100%", padding: "8px", marginTop: "5px" }}
          />
        </div>

        <button type="submit" style={{ padding: "10px 20px", cursor: "pointer" }}>
          Download
        </button>
      </form>

      {message && <p style={{ marginTop: "20px", fontWeight: "bold" }}>{message}</p>}
    </div>
  );
}

export default App;
