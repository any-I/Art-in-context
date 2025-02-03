import React, { useState } from "react";

function App() {
  const [artworkName, setArtworkName] = useState("");
  const [artworkData, setArtworkData] = useState(null);
  const [error, setError] = useState("");

  const getArtwork = async () => {
    if (!artworkName) {
      setError("Please enter an artwork name!");
      return;
    }

    try {
      const response = await fetch(`http://localhost:8080/api/artwork?name=${encodeURIComponent(artworkName)}`);
      if (!response.ok) throw new Error("error getting artwork details");

      const data = await response.json();
      console.log("API response data: ", data)

      if (data.error) {
        setError(data.error);
        setArtworkData(null);
      } else {
        setArtworkData(data);
        setError("");
      }
    } catch (err) {
      console.error("Fetch Error:", err);
      setError("Load failed");
      setArtworkData(null);
    }
  };

  return (
      <div className="App">
        <h1>Artwork Search</h1>
        <input
            type="text"
            placeholder="Enter artwork name"
            value={artworkName}
            onChange={(e) => setArtworkName(e.target.value)}
        />
        <button onClick={getArtwork}>Search</button>

        {error && <p style={{ color: "red" }}>{error}</p>}

        {artworkData && (
            <div>
              <h2>{artworkData.title || "Unknown Title"}</h2>
              <p><strong>Artist:</strong> {artworkData.artistDisplayName || "Unknown"}</p>
              <p><strong>Date:</strong> {artworkData.objectDate || "Unknown"}</p>
              <p><strong>Medium:</strong> {artworkData.medium || "Unknown"}</p>
              <p><a href={artworkData.objectURL} target="_blank" rel="noopener noreferrer">View on Met Museum</a></p>
              {artworkData.primaryImage ? (
                  <img src={artworkData.primaryImage} alt={artworkData.title} width="300" />
              ) : (
                  <p>No image available</p>
              )}
            </div>
        )}
      </div>
  );
}

export default App;