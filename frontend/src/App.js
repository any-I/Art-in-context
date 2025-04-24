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
  const [error, setError] = useState(null);
  const [timelineData, setTimelineData] = useState([]);
  const [networkData, setNetworkData] = useState([]); // Add state for network data
  const [activeTimelineScope, setActiveTimelineScope] = useState(null); // Track scope for timeline title

  const agentSearch = async () => {
    setTimelineData([]);
    setNetworkData([]); // Clear network data on new search
    setError(null);
    setActiveTimelineScope(''); // Clear active scope indicator

    try {
      // Construct the request body
      const requestBody = {
        artistName: artistName,
        context: [scope] // Assuming 'scope' corresponds to the 'context' list expected by the backend
      };

      const response = await fetch(
        process.env.REACT_APP_API_URL || `http://artcontextengine.us-east-2.elasticbeanstalk.com/agent_search`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        }
      );

      if (!response.ok) {
        // Try to get more specific error from backend response if possible
        let errorData;
        try {
          errorData = await response.json();
        } catch (parseError) {
          // If response is not JSON or empty
          throw new Error(`HTTP error ${response.status}: Error performing AI search`);
        }
        throw new Error(errorData.detail || errorData.error || `HTTP error ${response.status}: Error performing AI search`);
      }

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        // Ensure data arrays are cleared on error
        setTimelineData([]); 
        setNetworkData([]);
      } 
      // --- Conditional Data Handling --- 
      else if ((scope === 'political-events' || scope === 'art-movements') && data.timelineEvents) {
          // Common handling for timeline-based scopes
          console.log(`Received timelineEvents for scope '${scope}':`, data.timelineEvents);
          const transformedData = (data.timelineEvents || []).map(event => ({
              // Map backend fields to Chrono fields
              title: event.date || "Date Missing", // Use 'date' for the timeline title
              cardTitle: event.summary || event.movement_name || "Event Summary Missing", // Use 'summary' or 'movement_name' for card title
              cardDetailedText: event.detailed_summary || event.movement_description || "Details Missing", // Use detailed descriptions
              // Append source URL if available
              cardDetailedTextWithSource: (event.detailed_summary || event.movement_description || "Details Missing") +
                                           (event.source_url ? `\n\n[Source](${event.source_url})` : ""),
              // Image handling
              media: event.artwork_image_url ? {
                  type: "IMAGE",
                  source: { url: event.artwork_image_url }
              } : undefined,
              // Map data (optional, might not exist for all events/scopes)
              latitude: event.latitude,
              longitude: event.longitude,
              // Include other relevant fields if needed by the frontend later
              rawEvent: event // Keep raw event data if needed elsewhere
          }));

          console.log("Transformed timeline data:", transformedData);
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
      } else {
        // Handle cases where data is missing for the expected scope
        console.warn(`Received response for scope '${scope}', but expected data field was missing or empty.`, data);
        setError(`Received response, but no valid data found for the '${getListTitle(scope)}' scope.`);
        setTimelineData([]);
        setNetworkData([]);
      }
      // ----------------------------------
    } catch (err) {
      console.error("Fetch error:", err); // Log the actual error
      setError(err.message || "Failed to perform AI search");
      setTimelineData([]);
      setNetworkData([]); // Clear network data on fetch error too
      setActiveTimelineScope(''); // Clear scope on error
    }
  }

  const getListTitle = (currentScope) => { // Modified to accept scope argument
    switch(currentScope) {
      case 'political-events': return 'Political Events';
      case 'art-movements': return 'Art Movements';
      case 'artist-network': return 'Artist Network';
      default: return 'Events'; // Fallback title
    }
  };

  return (
    <div className="app-container">
      <h1>Artist Context Engine</h1> {/* Updated Title */}

      <div className="search-form">
        <div className="form-group">
          <label>Artist Name</label>
          <input
            type="text"
            value={artistName}
            onChange={(e) => setArtistName(e.target.value)}
            placeholder="e.g., Vincent van Gogh" // Example text
          />
        </div>

        <div className="form-group">
          <label>Analysis Scope</label> {/* Updated Label */}
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="political-events">Political Events</option>
            <option value="art-movements">Art Movements</option>
            <option value="artist-network">Artist Network</option>
          </select>
        </div>

        <button onClick={agentSearch}>AI Search</button>
      </div>

      {error && <div className="error-message">Error: {error}</div>}

      {/* timeline and map container */}
      {timelineData && timelineData.length > 0 && (
        <div className="results-container timeline-map-container"> {/* Added classes */}
          <div className="timeline-section"> {/* Wrapper for timeline */}
            <h2>Timeline of {getListTitle(activeTimelineScope)}</h2>
            <div style={{ width: '100%', height: '450px' }}> {/* Adjusted height */}
              <Chrono
                // Use the transformed data, ensure fields match
                items={timelineData.map(item => ({
                    title: item.title, // Already mapped
                    cardTitle: item.cardTitle, // Already mapped
                    // Use cardDetailedTextWithSource for Chrono display
                    cardDetailedText: item.cardDetailedTextWithSource,
                    media: item.media, // Already mapped
                 }))}
                mode="VERTICAL_ALTERNATING" // Changed mode for potentially longer text
                scrollable={{ scrollbar: true }}
                enableOutline
                theme={{
                  primary: '#007bff', // Adjusted theme colors
                  secondary: '#e9ecef',
                  cardBgColor: '#ffffff',
                  cardForeColor: '#343a40',
                  titleColor: '#007bff',
                  titleColorActive: '#0056b3',
                }}
                fontSizes={{
                  cardText: '0.85rem', // Adjusted font sizes
                  cardTitle: '1rem',
                  title: '0.9rem',
                }}
                useReadMore={false} // Keep this false or manage state if true
              />
            </div>
          </div>

          <div className="map-section"> {/* Wrapper for map */}
            <h2>Geographical Context</h2> {/* Updated map title */}
            <MapContainer
              center={[20, 0]} // Default center
              zoom={2} // Default zoom
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
                      {/* Display the base detailed text in popup */}
                      <ReactMarkdown>{item.cardDetailedText || ''}</ReactMarkdown>
                    </Popup>
                  </Marker>
              ))}
            </MapContainer>
          </div>
        </div>
      )}

      {/* Network visualization */}
      {networkData && networkData.length > 0 && (
         <div className="results-container network-graph-container"> {/* Added class */}
             {/* Keep existing NetworkGraph component */}
            <NetworkGraph data={networkData} artistName={artistName} />
         </div>
      )}
    </div>
  );
}

export default App;