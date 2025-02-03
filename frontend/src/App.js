// import React, { useState } from "react";

// function App() {
//   const [artworkName, setArtworkName] = useState("");
//   const [artworkData, setArtworkData] = useState(null);
//   const [error, setError] = useState("");

//   const getArtwork = async () => {
//     if (!artworkName) {
//       setError("Please enter an artwork name!");
//       return;
//     }

//     try {
//       const response = await fetch(`http://localhost:8080/api/artwork?name=${encodeURIComponent(artworkName)}`);
//       if (!response.ok) throw new Error("error getting artwork details");

//       const data = await response.json();
//       console.log("API response data: ", data)

//       if (data.error) {
//         setError(data.error);
//         setArtworkData(null);
//       } else {
//         setArtworkData(data);
//         setError("");
//       }
//     } catch (err) {
//       console.error("Fetch Error:", err);
//       setError("Load failed");
//       setArtworkData(null);
//     }
//   };

//   return (
//       <div className="App">
//         <h1>Artwork Search</h1>
//         <input
//             type="text"
//             placeholder="Enter artwork name"
//             value={artworkName}
//             onChange={(e) => setArtworkName(e.target.value)}
//         />
//         <button onClick={getArtwork}>Search</button>

//         {error && <p style={{ color: "red" }}>{error}</p>}

//         {artworkData && (
//             <div>
//               <h2>{artworkData.title || "Unknown Title"}</h2>
//               <p><strong>Artist:</strong> {artworkData.artistDisplayName || "Unknown"}</p>
//               <p><strong>Date:</strong> {artworkData.objectDate || "Unknown"}</p>
//               <p><strong>Medium:</strong> {artworkData.medium || "Unknown"}</p>
//               <p><a href={artworkData.objectURL} target="_blank" rel="noopener noreferrer">View on Met Museum</a></p>
//               {artworkData.primaryImage ? (
//                   <img src={artworkData.primaryImage} alt={artworkData.title} width="300" />
//               ) : (
//                   <p>No image available</p>
//               )}
//             </div>
//         )}
//       </div>
//   );
// }

// export default App;

import React, { useState } from "react";

function App() {
  const [artworkName, setArtworkName] = useState("");
  const [artworkList, setArtworkList] = useState([]);
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
      console.log("API response data: ", data);

      if (data.error) {
        setError(data.error);
        setArtworkList([]);
      } else {
        setArtworkList(data);
        setError("");
      }
    } catch (err) {
      console.error("Fetch Error:", err);
      setError("Load failed");
      setArtworkList([]);
    }
  };

  return (
    <div className="App" style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center',
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '20px'
    }}>
      <h1>Art Context Engine with AI</h1>
      <div style={{ marginBottom: '20px' }}>
        <input
          type="text"
          placeholder="Enter artwork name"
          value={artworkName}
          onChange={(e) => setArtworkName(e.target.value)}
          style={{ marginRight: '10px', padding: '5px' }}
        />
        <button onClick={getArtwork}>Search</button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '20px',
        width: '100%'
      }}>
        {artworkList.map((artwork, index) => (
          <div key={index} style={{ 
            border: '1px solid #ccc',
            borderRadius: '8px',
            padding: '1rem',
            textAlign: 'left'
          }}>
            <h2 style={{ fontSize: '1.2rem', marginTop: '0' }}>{artwork.title || "Unknown Title"}</h2>
            <p><strong>Artist:</strong> {artwork.artistDisplayName || "Unknown"}</p>
            <p><strong>Date:</strong> {artwork.objectDate || "Unknown"}</p>
            <p><strong>Medium:</strong> {artwork.medium || "Unknown"}</p>
            <p><a href={artwork.objectURL} target="_blank" rel="noopener noreferrer">View on Met Museum</a></p>
            {artwork.primaryImage ? (
              <img 
                src={artwork.primaryImage} 
                alt={artwork.title} 
                style={{ 
                  width: '100%', 
                  height: '200px',
                  objectFit: 'contain'
                }} 
              />
            ) : (
              <p>No image available</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;