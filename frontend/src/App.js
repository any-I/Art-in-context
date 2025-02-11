import React, { useState } from 'react';
import './App.css';

const App = () => {
  const [artistName, setArtistName] = useState("");
  const [currentScope, setCurrentScope] = useState("");
  const [scopes, setScopes] = useState([]);
  const [artistUrl, setArtistUrl] = useState("");
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");

  const addScope = () => {
    if (currentScope.trim()) {
      setScopes([...scopes, currentScope.trim()]);
      setCurrentScope("");
    }
  };

  const removeScope = (indexToRemove) => {
    setScopes(scopes.filter((_, index) => index !== indexToRemove));
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addScope();
    }
  };

  const searchArtist = async () => {
    if (!artistName) {
      setError("Please enter an artist name");
      return;
    }

    try {
      const queryParams = new URLSearchParams({
        name: artistName,
        scopes: JSON.stringify(scopes)
      });

      const response = await fetch(
        `http://localhost:8080/api/artwork?${queryParams}`
      );
      
      if (!response.ok) throw new Error("Error searching artist");

      const data = await response.json();
      
      if (data.error) {
        setError(data.error);
        setArtistUrl("");
        setEvents([]);
      } else {
        setArtistUrl(data.artistUrl);
        setEvents(data.events || []);
        setError("");
      }
    } catch (err) {
      setError("Failed to search artist");
      setArtistUrl("");
      setEvents([]);
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
          <label>Add Scopes</label>
          <div className="scope-input">
            <input
              type="text"
              value={currentScope}
              onChange={(e) => setCurrentScope(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Enter a scope"
            />
            <button
              onClick={addScope}
              className="add-scope-btn"
            >
              +
            </button>
          </div>
          
          {scopes.length > 0 && (
            <div className="scope-tags">
              {scopes.map((scope, index) => (
                <div
                  key={index}
                  className="scope-tag"
                >
                  <span>{scope}</span>
                  <button
                    onClick={() => removeScope(index)}
                    className="remove-scope-btn"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={searchArtist}
          className="search-btn"
        >
          Search
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      
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
              <h3>Related Information</h3>
              {events.map((event, index) => (
                <div key={index} className="event-item">
                  <h4>
                    <a
                      href={event.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
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
};

export default App;