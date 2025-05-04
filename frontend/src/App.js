import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import "./App.css";
import { Chrono } from "react-chrono";
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import NetworkGraph from './NetworkGraph'; // Import NetworkGraph
import { OpenStreetMapProvider } from 'leaflet-geosearch'; // Corrected Geocoding provider
import 'leaflet-geosearch/dist/geosearch.css'; // Import Geocoding CSS
import 'react-vertical-timeline-component/style.min.css'; // Keep existing imports

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
  const [activeTimelineScope, setActiveTimelineScope] = useState(null); // Added state for active timeline scope
  const [isLoading, setIsLoading] = useState(false); // State for loading status
  const [loadingTime, setLoadingTime] = useState(0); // State for loading time
  const [mapMarkers, setMapMarkers] = useState([]); // State for processed map markers
  const [genreResult, setGenreResult] = useState(''); // New state for Genre scope
  const timerRef = useRef(null); // Ref to store timer interval ID
 
  // Cleanup timer on component unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // Helper function to extract the earliest year for sorting
  const parseDateForSort = (dateString) => {
    if (!dateString) return Infinity; // Place items without dates at the end

    // Handle ranges like "Early 1930s" or "1930s-1940s"
    // Ignores optional leading text like "Early ", "Late " etc.
    const rangeMatch = dateString.match(/(?:\b\w+\s+)?(\d{4})s?(?:-(\d{4})s?)?$/);
    if (rangeMatch) {
      return parseInt(rangeMatch[1], 10); // Takes the first year in a range
    }

    // Handle single year or more specific dates, ignoring leading text
    const yearMatch = dateString.match(/\b(\d{4})\b/);
    if (yearMatch) {
      return parseInt(yearMatch[1], 10);
    }

    // If no year is found, treat as undated
    return Infinity;
  };

  // --- Geocoding Effect ---
  useEffect(() => {
    const geocodeLocations = async () => {
      if (!timelineData || timelineData.length === 0) {
        console.log("[GEOCODE] timelineData empty, clearing markers.");
        setMapMarkers([]);
        return;
      }

      console.log("[GEOCODE] Processing timelineData:", JSON.parse(JSON.stringify(timelineData))); // Deep copy for logging

      const provider = new OpenStreetMapProvider();
      // Store promises and their corresponding original items
      const geocodingRequests = []; // Array of { promise, originalItem }
      const processedMarkers = []; // Markers with lat/lon already

      timelineData.forEach(item => {
        if (item.latitude != null && item.longitude != null) {
          // If lat/lon exist, use them directly
          // Ensure key includes something unique even if title is missing
          processedMarkers.push({ ...item, key: `${item.latitude}-${item.longitude}-${item.title || 'no-title'}` }); 
        } else if (item.location_name) {
          // If location exists, create a geocoding promise
          geocodingRequests.push({
            promise: provider.search({ query: item.location_name }),
            originalItem: item
          });
        } else if (item.latitude == null && item.longitude == null && !item.location_name) {
          console.warn("[GEOCODE] Item lacks coordinates and location_name:", item);
        }
        // Ignore items with neither coordinates nor location
      });

      // Extract just the promises for Promise.allSettled
      const promises = geocodingRequests.map(req => req.promise);
      // Wait for all geocoding requests to settle
      const settledResults = await Promise.allSettled(promises);

      // Process settled results using the index to map back to the original item
      settledResults.forEach((result, index) => {
        const { originalItem } = geocodingRequests[index]; // Get the corresponding original item

        if (result.status === 'fulfilled') {
          const providerResultsArray = result.value; // Direct result from provider.search
          console.log(`[GEOCODE] Raw result for '${originalItem.location_name}':`, JSON.parse(JSON.stringify(providerResultsArray))); // Log raw result
          if (providerResultsArray && providerResultsArray.length > 0) {
            const geoResult = providerResultsArray[0]; // Use the first result
            console.log(`[GEOCODE] Geocoded '${originalItem.location_name}' to Lat: ${geoResult.y}, Lon: ${geoResult.x}`);
            processedMarkers.push({
              ...originalItem,
              latitude: geoResult.y,
              longitude: geoResult.x,
              // Use index in key for geocoded items to ensure uniqueness
              key: `${geoResult.y}-${geoResult.x}-${originalItem.title || 'no-title'}-${index}` 
            });
          } else {
            console.warn(`[GEOCODE] No results found for '${originalItem.location_name}'.`);
          }
        } else { // result.status === 'rejected'
          console.error(`[GEOCODE] Geocoding FAILED for '${originalItem.location_name}':`, result.reason);
        }
      });

      console.log("[GEOCODE] Final processedMarkers before state update:", JSON.parse(JSON.stringify(processedMarkers)));
      setMapMarkers(processedMarkers);
    };

    geocodeLocations();

  }, [timelineData]); // Rerun when timelineData changes

  const agentSearch = async () => {
    setIsLoading(true);
    setLoadingTime(0);
    // Clear previous timer if any
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    // Start new timer
    timerRef.current = setInterval(() => {
      setLoadingTime(prevTime => prevTime + 1);
    }, 1000);

    setTimelineData([]);
    setNetworkData([]); // Clear network data on new search
    setError(null);
    setActiveTimelineScope(''); // Clear active scope indicator
    setGenreResult(''); // Reset genre result

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
        setGenreResult('');
      } 
      // --- Conditional Data Handling --- 
      else if (scope === 'political-events' && data.timelineEvents) {
        console.log("Received timelineEvents for Political Events:", data.timelineEvents); 
        console.log('[AGENT_SEARCH] Data before setTimelineData:', JSON.parse(JSON.stringify(data.timelineEvents)));
        let transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          location_name: event.location_name, // Include location_name
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

        // Sort chronologically based on the earliest year found in the date
        transformedData.sort((a, b) => parseDateForSort(a.title) - parseDateForSort(b.title));
        console.log('[AGENT_SEARCH] Sorted Political Events Data:', JSON.parse(JSON.stringify(transformedData)));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data when timeline is loaded
        setActiveTimelineScope(scope); // Update active scope on success
      }

      else if (scope === 'art-movements' && data.timelineEvents) { 
        console.log("Received timelineEvents for Art Movements:", data.timelineEvents);
        let transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          location_name: event.location_name, // Include location_name
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
        
        // Sort chronologically based on the earliest year found in the date
        transformedData.sort((a, b) => parseDateForSort(a.title) - parseDateForSort(b.title));
        console.log('[AGENT_SEARCH] Sorted Art Movements Data:', JSON.parse(JSON.stringify(transformedData)));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data
        setActiveTimelineScope(scope); // Update active scope
      }

      else if (scope === 'artist-network' && data.networkData) {
        console.log("Received networkData:", data.networkData); 
        setNetworkData(data.networkData);
        setTimelineData([]); // Clear timeline data when network is loaded
      }

      else if (scope === 'personal-events' && data.timelineEvents) {
        console.log("Received timelineEvents for Personal Events:", data.timelineEvents); 
        console.log('[AGENT_SEARCH] Data before setTimelineData:', JSON.parse(JSON.stringify(data.timelineEvents)));
        let transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          location_name: event.location_name, // Include location_name
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

        // Sort chronologically based on the earliest year found in the date
        transformedData.sort((a, b) => parseDateForSort(a.title) - parseDateForSort(b.title));
        console.log('[AGENT_SEARCH] Sorted Personal Events Data:', JSON.parse(JSON.stringify(transformedData)));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data when timeline is loaded
        setActiveTimelineScope(scope); // Update active scope on success
      }

      else if (scope === 'economic-events' && data.timelineEvents) {
        console.log("Received timelineEvents for Economic Events:", data.timelineEvents); 
        console.log('[AGENT_SEARCH] Data before setTimelineData:', JSON.parse(JSON.stringify(data.timelineEvents)));
        let transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          location_name: event.location_name, // Include location_name
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

        // Sort chronologically based on the earliest year found in the date
        transformedData.sort((a, b) => parseDateForSort(a.title) - parseDateForSort(b.title));
        console.log('[AGENT_SEARCH] Sorted Economic Events Data:', JSON.parse(JSON.stringify(transformedData)));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data when timeline is loaded
        setActiveTimelineScope(scope); // Update active scope on success
      }

      else if (scope === 'genre' && data.timelineEvents) {
        console.log("Received timelineEvents for Genre:", data.timelineEvents); 
        console.log('[AGENT_SEARCH] Data before setTimelineData:', JSON.parse(JSON.stringify(data.timelineEvents)));
        let transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          location_name: event.location_name, // Include location_name
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

        // Sort chronologically based on the earliest year found in the date
        transformedData.sort((a, b) => parseDateForSort(a.title) - parseDateForSort(b.title));
        console.log('[AGENT_SEARCH] Sorted Genre Data:', JSON.parse(JSON.stringify(transformedData)));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data when timeline is loaded
        setActiveTimelineScope(scope); // Update active scope on success
      }

      else if (scope === 'medium' && data.timelineEvents) {
        console.log("Received timelineEvents for Medium:", data.timelineEvents); 
        console.log('[AGENT_SEARCH] Data before setTimelineData:', JSON.parse(JSON.stringify(data.timelineEvents)));
        let transformedData = (data.timelineEvents || []).map(event => ({
          title: event.date, 
          cardTitle: event.event_title,
          location_name: event.location_name, // Include location_name
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

        // Sort chronologically based on the earliest year found in the date
        transformedData.sort((a, b) => parseDateForSort(a.title) - parseDateForSort(b.title));
        console.log('[AGENT_SEARCH] Sorted Medium Data:', JSON.parse(JSON.stringify(transformedData)));

        setTimelineData(transformedData);
        setNetworkData([]); // Clear network data when timeline is loaded
        setActiveTimelineScope(scope); // Update active scope on success
      }

      else {
        // Handle cases where data is missing for the expected scope
        console.warn(`Data key ('${scope === 'political-events' ? 'timelineEvents' : 'networkData'}') not found in response for scope '${scope}'.`);
        setError(`Received response, but no valid data found for the selected scope.`);
        setTimelineData([]);
        setNetworkData([]);
        setGenreResult('');
      }
      // ----------------------------------
    } catch (err) {
      setError(err.message || "Failed to perform AI search");
      setTimelineData([]);
      setNetworkData([]); // Clear network data on fetch error too
      setGenreResult('');
    }
    finally {
      setIsLoading(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }

  const getListTitle = (currentScope) => { // Modified to accept scope argument
    switch(currentScope) {
      case 'political-events': return 'Political Events';
      case 'art-movements': return 'Art Movements';
      case 'artist-network': return 'Artist Network';
      case 'personal-events': return 'Personal Life Events'; 
      case 'economic-events': return 'Economic Context'; 
      case 'genre': return 'Genre'; 
      case 'medium': return 'Medium'; 
      default: return 'Network Graph'; // Default or adjust as needed
    }
  };

  return (
    <div className="app-container">
      <h1 style={{ textAlign: 'center'}}>Art Historical Context Engine with AI</h1>
      
      <div className="search-form">
        <div className="form-group">
          <label>Artist Name</label>
          <input
            type="text"
            value={artistName}
            onChange={(e) => setArtistName(e.target.value)}
            placeholder="e.g. Vincent van Gogh"
          />
        </div>
        
        <div className="form-group">
          <label>Search Scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="artist-network">Artist Network (Graph)</option>
            <option value="political-events">Political Events (Timeline, Map)</option>
            <option value="economic-events">Economic Events (Timeline, Map)</option>
            <option value="art-movements">Art Movements (Timeline, Map)</option>
            <option value="personal-events">Personal Events (Timeline, Map)</option>
            <option value="genre">Artist Genre (Timeline, Map)</option>
            <option value="medium">Artist Medium (Timeline, Map)</option>
          </select>
        </div>

        <button onClick={agentSearch}>Search</button>
      </div>

      {/* Loading Indicator */}
      {isLoading && (
        <div style={{ textAlign: 'center', marginTop: '10px', color: '#555' }}>
          Loading... ({loadingTime}s elapsed)
        </div>
      )}

      {error && <div className="error-message">Error: {error}</div>}

      {/* Genre Result Display (New) */}
      {genreResult && scope === 'Genre' && (
        <div className="genre-result result-box"> 
          <h2>{getListTitle(scope)}</h2> 
          <p><strong>{artistName}</strong> is associated with the genre: <strong>{genreResult}</strong></p>
        </div>
      )}

      {/* timeline stuff */}
      {timelineData && timelineData.length > 0 && (
        <div className="timeline-container" style={{ width: '100%', height: 'auto', marginTop: '20px', marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}> 
          <div> 
            <h2 style={{ textAlign: 'center' }}>Timeline</h2>
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
            <h2 style={{ textAlign: 'center' }}>Map</h2>
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
              {mapMarkers
                .filter(item => item.latitude != null && item.longitude != null) 
                .map((item) => ( // Use item.key instead of index
                  <Marker key={item.key} position={[item.latitude, item.longitude]}>
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
    </div>
  );
}

export default App;