import React, { useState } from "react";
import ReactMarkdown from 'react-markdown';

import "./App.css";
import { Chrono } from "react-chrono";  // for timeline visualization (can change to other library later)

function App() {
  const [artistName, setArtistName] = useState("");
  const [scope, setScope] = useState("political-events"); 
  const [artistUrl, setArtistUrl] = useState("");
  const [error, setError] = useState(null);
  const [timelineData, setTimelineData] = useState([]); 
 
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
        setError("");
      } 
      
      else {
        setArtistUrl(data.artistUrl);
        setError("");
      }
    } catch (err) {
      setError("Failed to search artist");
      setArtistUrl("");
    }
  };

  const agentSearch = async () => {
    setTimelineData([]);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8080/api/agent?artistName=${artistName}&context=${scope}`
      );

      if (!response.ok) throw new Error("Error performing AI search");

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setTimelineData([]);
      } 
      
      else {
        const transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          cardDetailedText: event.detailed_summary + (event.source_url ? `\n\n[Source](${event.source_url})` : ""), 
          
          // images to show up in timeline where needed
          media: event.artwork_image_url ? {
            type: "IMAGE",
            source: {
              url: event.artwork_image_url
            }
          } : undefined
        }));

        setTimelineData(transformedData);
      }
    } catch (err) {
      setError(err.message || "Failed to perform AI search");
      setTimelineData([]);
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
        <button onClick={agentSearch}>AI Search</button>
      </div>

      {error && <div className="error-message">Error: {error}</div>}

      {/* timeline stuff */}
      {timelineData && timelineData.length > 0 && (
        <div className="timeline-container" style={{ width: '100%', height: '600px', marginTop: '20px', marginBottom: '20px' }}>
          <h2>Timeline of {getListTitle()}</h2>
          <Chrono
            items={timelineData}
            mode="VERTICAL" 
            scrollable={{ scrollbar: true }} 
            enableOutline
            mediaHeight={500}  // TODO: don't know how to set this dynamically
            theme={{ 
              primary: 'rgb(33, 150, 243)',
              secondary: 'white',
              cardBgColor: 'rgb(240, 240, 240)',
              cardForeColor: '#333',
              titleColor: 'black',
              titleColorActive: 'rgb(33, 150, 243)',
            }}
            fontSizes={{ 
              cardText: '0.9rem',
              cardTitle: '1rem',
              title: '1rem',
            }}
            useReadMore={false} 
          />
        </div>
      )}

      {/* idk what this does and if we need it */}
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
        </div>
      )}
    </div>
  );
}

export default App;