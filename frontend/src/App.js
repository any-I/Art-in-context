import React, { useState } from "react";
import ReactMarkdown from 'react-markdown';
import "./App.css";
import { Chrono } from "react-chrono";
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import NetworkGraph from './NetworkGraph'; // Import NetworkGraph

// Fix for default marker icon issue with Webpack
import L from 'leaflet';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetinaUrl,
  iconUrl: iconUrl,
  shadowUrl: shadowUrl,
});
// End of fix

function App() {
  const [artistName, setArtistName] = useState("");
  const [scope, setScope] = useState("political-events"); 
  const [artistUrl, setArtistUrl] = useState("");
  const [error, setError] = useState(null);
  const [timelineData, setTimelineData] = useState([]); 
  const [networkData, setNetworkData] = useState([]); // Add state for network data
  const [activeTimelineScope, setActiveTimelineScope] = useState(null); // Added state for active timeline scope
 
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
    setNetworkData([]); // Clear network data on new search
    setError(null);
    setActiveTimelineScope(''); // Clear active scope indicator

    try {
      const response = await fetch(
        `http://localhost:8080/api/agent?artistName=${artistName}&context=${scope}`
      );

      if (!response.ok) throw new Error("Error performing AI search");

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        // Ensure data arrays are cleared on error
        setTimelineData([]); 
        setNetworkData([]);
      } 
      // --- Conditional Data Handling --- 
      else if (scope === 'political-events' && data.timelineEvents) {
        console.log("Received timelineEvents:", data.timelineEvents); 
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
          } : undefined,
          latitude: event.latitude,
          longitude: event.longitude
        }));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data when timeline is loaded
        setActiveTimelineScope(scope); // Update active scope on success
      }
      else if (scope === 'artist-network' && data.networkData) {
        console.log("Received networkData:", data.networkData); 
        // Assuming networkData is already in a usable format for the graph
        // We might add transformation logic here later if needed
        setNetworkData(data.networkData);
        setTimelineData([]); // Clear timeline data when network is loaded
        // We might need a separate state for active network scope later
        // setActiveTimelineScope(''); // Or set a different state like setActiveVisualizationType('network')
      }
      else {
        // Handle cases where data is missing for the expected scope
        console.warn(`Data key ('${scope === 'political-events' ? 'timelineEvents' : 'networkData'}') not found in response for scope '${scope}'.`);
        setError(`Received response, but no valid data found for the selected scope.`);
        setTimelineData([]);
        setNetworkData([]);
      }
      // ----------------------------------
    } catch (err) {
      setError(err.message || "Failed to perform AI search");
      setTimelineData([]);
      setNetworkData([]); // Clear network data on fetch error too
    }
  }

  const getListTitle = (currentScope) => { // Modified to accept scope argument
    switch(currentScope) {
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
        <div className="timeline-container" style={{ width: '100%', height: 'auto', marginTop: '20px', marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}> 
          <div> 
            <h2>Timeline of {getListTitle(activeTimelineScope)}</h2>
            <div style={{ width: '100%', height: '400px' }}> 
              <Chrono
                items={timelineData.map(item => ({ ...item, title: item.title || 'Date Missing' }))}
                mode="HORIZONTAL"
                scrollable={{ scrollbar: true }}
                enableOutline
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
          </div>
          
          <div> 
            <h2>Map</h2>
            <MapContainer 
              center={[20, 0]} 
              zoom={2} 
              scrollWheelZoom={true} 
              style={{ height: '400px', width: '100%' }} 
              worldCopyJump={false} 
              maxBounds={[[-90, -180], [90, 180]]} 
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {timelineData
                .filter(item => item.latitude != null && item.longitude != null) 
                .map((item, index) => (
                  <Marker key={index} position={[item.latitude, item.longitude]}>
                    <Popup>
                      <b>{item.cardTitle || 'Event'}</b><br />
                      {item.title || 'Date Missing'} <br /> 
                      {item.cardDetailedText.split('\n')[0]} 
                    </Popup>
                  </Marker>
              ))}
            </MapContainer>
          </div>
        </div>
      )}

      {/* Network visualization */}
      {networkData && networkData.length > 0 && (
        <NetworkGraph data={networkData} artistName={artistName} />
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