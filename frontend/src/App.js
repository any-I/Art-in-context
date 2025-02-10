import React, { useState } from "react";

function App() {
  const [artistName, setArtistName] = useState("");
  const [artistUrl, setArtistUrl] = useState("");
  const [error, setError] = useState("");

  const searchArtist = async () => {
    if (!artistName) {
      setError("Please enter an artist name");
      return;
    }

    try {
      const response = await fetch(`http://localhost:8080/api/artwork?name=${encodeURIComponent(artistName)}`);
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
    <div className="flex flex-col items-center p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Artist Search</h1>
      
      <div className="w-full flex gap-4 mb-6">
        <input
          type="text"
          value={artistName}
          onChange={(e) => setArtistName(e.target.value)}
          placeholder="Enter artist name"
          className="flex-1 p-2 border rounded"
        />
        <button 
          onClick={searchArtist}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Search
        </button>
      </div>

      {error && <p className="text-red-500 mb-4">{error}</p>}
      
      {artistUrl && (
        <a 
          href={artistUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:underline"
        >
          View Artist on Wikipedia
        </a>
      )}
    </div>
  );
}

export default App;