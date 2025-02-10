import React, { useState } from "react";
import "./App.css";

function App() {
  const [artistName, setArtistName] = useState("");
  const [scope, setScope] = useState("political-events");
  const [artistUrl, setArtistUrl] = useState("");
  const [error, setError] = useState("");

  const searchArtist = async () => {
    if (!artistName) {
      setError("Please enter an artist name");
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8080/api/artwork?name=${encodeURIComponent(artistName)}&scope=${scope}`
      );
      if (!response.ok) throw new Error("Error searching artist");

      const data = await response.json();
      
      if (data.error) {
        setError(data.error);
        setArtistUrl("");
      } else {
        setArtistUrl(data.url);
        setError("");
      }
    } catch (err) {
      setError("Failed to search artist");
      setArtistUrl("");
    }
  };

  return (
    <div className="app-container">
      <h1>Artist Timeline Explorer</h1>
      
      <div className="search-form">
        <div className="form-group">
          <label>Artist Name</label>
          <input
            type="text"
            value={artistName}
            onChange={(e) => setArtistName(e.target.value)}
            placeholder="Enter artist name"
          />
        </div>
        
        <div className="form-group">
          <label>Search Scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="political-events">Political Events</option>
            <option value="art-movements">Art Movements</option>
            <option value="personal-events">Personal Events</option>
            <option value="artist-network">Artist Network</option>
          </select>
        </div>

        <button onClick={searchArtist}>Search</button>
      </div>

      {error && <div className="error">{error}</div>}
      
      {artistUrl && (
        <div className="result">
          <a 
            href={artistUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            View Artist Details on Wikipedia
          </a>
        </div>
      )}
    </div>
  );
}

export default App;