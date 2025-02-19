import React, { useState } from "react";
import "./App.css";

function App() {
  const [artistName, setArtistName] = useState("");
  const [scope, setScope] = useState("political-events");
  const [artistUrl, setArtistUrl] = useState("");
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [searchID, setSearchID] = useState("");
  const [searchSummary, setSearchSummary] = useState("");

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
        setEvents([]);
        setSearchID("");
      } else {
        setArtistUrl(data.artistUrl);
        setEvents(data.events || []);
        setError("");
        setSearchID(data.searchID);
      }
      setSearchSummary("");
    } catch (err) {
      setError("Failed to search artist");
      setArtistUrl("");
      setEvents([]);
      setSearchID("");
      setSearchSummary("");
    }
  };

  const summarizeSearch = async () => {
    try {
      const response = await fetch(
        `http://localhost:8080/api/summarize?searchID=${searchID}&artistName=${artistName}`
      );
      if (!response.ok) throw new Error("Error summarizing search results");

      const data = await response.json();

      if (data.error) {
        setSearchSummary("");
      } else {
        setSearchSummary(data.summary);
      }
    } catch (err) {
      setSearchSummary("");
    }
  }

  const getListTitle = () => {
    switch(scope) {
      case 'political-events': return 'Political Events';
      case 'art-movements': return 'Art Movements';
      case 'artist-network': return 'Artist Network';
      default: return 'Events';
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
            <option value="artist-network">Artist Network</option>
          </select>
        </div>

        <button onClick={searchArtist}>Search</button>

        {artistUrl && <button onClick={summarizeSearch}>Summarize</button>}
      </div>

      {error && <div className="error">{error}</div>}

      {searchSummary && (
        <div className="summary">
          <h2>Summary</h2>
          <div className="summary-text">
            <p>{searchSummary}</p>
          </div>
        </div>
      )}
      
      {artistUrl && (
        <div className="result">
          <h2>Artist Information</h2>
          <a 
            href={artistUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            View Artist Details on Wikipedia
          </a>
          
          {events.length > 0 && (
            <div className="events-list">
              <h3>Related {getListTitle()}</h3>
              {events.map((event, index) => (
                <div key={index} className="event-item">
                  <h4>
                    <a href={event.url} target="_blank" rel="noopener noreferrer">
                      {event.title}
                    </a>
                  </h4>
                  <p dangerouslySetInnerHTML={{ __html: event.snippet }} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;