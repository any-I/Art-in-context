import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import "./App.css";
import { Chrono } from "react-chrono";
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import NetworkGraph from './NetworkGraph'; // Import NetworkGraph
import 'leaflet-geosearch/dist/geosearch.css'; // Import Geocoding CSS
import 'react-vertical-timeline-component/style.min.css'; // Keep existing imports
import "slick-carousel/slick/slick.css";
import "slick-carousel/slick/slick-theme.css";
import {performSearch} from './searchHelpers';
import {geocodeLocations} from './geocodeHelper';
import Gallery from './Gallery';

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

// Helper functions/info to do with maintaining scopes
// scopeInfo is made into a Map to guarantee ordering of the keys
// the name is how it appears in the dropdown, and by default this is 
// what is printed above the output, too, unless "output-title" is also
// specified
const scopeInfo = new Map([
  ["artist-network", {
    "name": "Artist Network",
    "output-title": "Network Graph",
    "output-type": ["Graph"]
  }],
  ["political-events", {
    "name": "Political Events",
    "output-type": ["Timeline", "Map"]
  }],
  ["art-movements", {
    "name": "Art Movements",
    "output-type": ["Timeline", "Map"]
  }],
  ["personal-events", {
    "name": "Personal Events",
    "output-title": "Personal Life Events",
    "output-type": ["Timeline", "Map"]
  }],
  ["economic-events", {
    "name": "Economic Events",
    "output-title": "Economic Context",
    "output-type": ["Timeline", "Map"]
  }],
  ["genre", {
    "name": "Genre",
    "output-type": ["Timeline", "Map"]
  }],
  ["medium", {
    "name": "Medium",
    "output-type": ["Timeline", "Map"]
  }]
]);

function getListTitle(scope){
  if(scopeInfo.has(scope)){
    const titleKey = "output-title" in scopeInfo.get(scope) ? "output-title":"name";
    return scopeInfo.get(scope)[titleKey];
  }
  return "";
}

//gets the iterator to the first valid scope depending on mode of search
//we skip the artist network scope (first key) if there's an artwork title
//otherwise, we start from the very beginning
function getFirstScopeIterator(hasArtworkTitle){
  const it = scopeInfo.keys();
  if(hasArtworkTitle){
    return it.drop(1);
  }
  return it;
}

//gets a list of options for scope selection depending on whether we're
//searching with artwork title or not
function getOptionsList(hasArtworkTitle){
  const curKey = getFirstScopeIterator(hasArtworkTitle);
  const optionItems = [];
  curKey.forEach((key) => {
    const info = scopeInfo.get(key);
    const labelText = info["name"] + " (" + info["output-type"].join(", ") + ")";
    optionItems.push(<option key = {key} value = {key}>{labelText}</option>);
  });
  return <>{optionItems}</>;
}

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
  const timerRef = useRef(null); // Ref to store timer interval ID
  const [artworkTitleOn, setArtworkTitleOn] = useState(false); // State for artwork search activated
  const [artworkTitle, setArtworkTitle] = useState(""); // State for artwork search input
 
  // Cleanup timer on component unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // --- Geocoding Effect ---
  useEffect(() => {
    geocodeLocations({ timelineData, setMapMarkers });
  }, [timelineData]); // Rerun when timelineData changes

  return (
    <div className="app-container">
      <h1 id = "app-title">Art in Context</h1>

      <Gallery setArtistName={setArtistName}></Gallery>
      <div className="search-form">
        <div className="form-group">
          <label className="label-item" htmlFor="artist-name">Artist Name</label>
          <input
              type="text"
              value={artistName}
              onChange={(e) => setArtistName(e.target.value)}
              placeholder="e.g. Vincent van Gogh"
              id="artist-name"
              className="form-control"
          />
        </div>

        <button
            className="form-control bg-transparent hover:bg-gray-100 transition-colors"
            onClick={() => {
              const newHasArtworkTitle = !artworkTitleOn;
              setArtworkTitleOn(newHasArtworkTitle); 
              setArtworkTitle("");
              //reset scope to the first "available" scope - prevents
              //someone from being on artist-network, switching to having an artwork title,
              //and then searching
              const firstScope = getFirstScopeIterator(newHasArtworkTitle);
              setScope(firstScope.next().value);
            }}>
          {artworkTitleOn ? (
              <span className="has-span-icon">
                <span className="span-icon text-red-500">✖</span> Remove Artwork Title
              </span>
            ) : (
              <span className="has-span-icon">
                  <span className="span-icon text-green-500 font-extrabold text-xl">+</span> Add Artwork Title (optional)
              </span>
          )}
        </button>

        {artworkTitleOn && (
            <div className="form-group">
              <label className="label-item" htmlFor="artwork-title">Artwork Title</label>
              <input
                  type="text"
                  value={artworkTitle}
                  onChange={(e) => setArtworkTitle(e.target.value)}
                  placeholder="e.g. Mona Lisa"
                  id="artwork-title"
                  className="form-control"
              />
            </div>
        )}

        <div className="form-group">
          <label className="label-item" htmlFor="scope-select">Search Scope</label>
          <select
              id = "scope-select"
              className="form-control"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
          >
            {getOptionsList(artworkTitleOn)}
          </select>
        </div>

        <button id="search-button"
            className="form-control"
            onClick={() => {
          let searchParams = {
            "scope": scope,
            "artistName": artistName
          };
          if (artworkTitleOn && artworkTitle !== "" && artworkTitle.toLowerCase() !== "untitled") {
            searchParams["artworkTitle"] = artworkTitle;
          } 
          performSearch(
            searchParams,
            setIsLoading,
            setLoadingTime,
            timerRef,
            setTimelineData,
            setNetworkData,
            setError,
            setActiveTimelineScope
          );
        }}>
          Search</button>
      </div>

      {/* Loading Indicator */}
      {isLoading && (
          <div className = "result-container" style={{textAlign: 'center'}}>
            Loading... ({loadingTime}s elapsed)
          </div>
      )}

      {error && <div className="error-message result-container"><p>Error: {error}</p></div>}

      {/* timeline and map result*/}
      {timelineData.length > 0 && (<>
        <div className = "result-container"> 
          <h2 style={{ textAlign: 'center' }}>{getListTitle(activeTimelineScope)}</h2>
          <div id = "timeline-container"> 
            <Chrono
              items={timelineData.map(item => ({ ...item, title: item.title || 'Date Missing' }))}
              mode="HORIZONTAL"
              scrollable={{ scrollbar: true }}
              enableOutline
              theme={{
                primary: 'var(--main-col)',
                secondary: 'white',
                buttonHoverBgColor: 'var(--accent-col)',
                cardBgColor: 'white', //card styling
                cardTitleColor: 'var(--main-col)',
                cardDetailsColor: 'var(--dark-text-col)',
                titleColor: 'var(--dark-text-col)', //timeline styling
                titleColorActive: 'var(--main-col)'
              }}
              fontSizes={{
                cardText: '0.9rem',
                cardTitle: '1rem',
                title: '1rem',
              }}
              useReadMore={false}
              parseDetailsAsHTML={true}
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
      </>)}

      {/* Network visualization */}
      {networkData.length > 0 && (
        <div className="result-container" style={{ width: '100%', height: '80vh' }}> 
          <h2>Artist Network</h2>
          <NetworkGraph data={networkData} artistName={artistName} />
        </div>
      )}
    </div>
  );
}

export default App;