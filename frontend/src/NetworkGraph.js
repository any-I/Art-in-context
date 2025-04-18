import React, { useState, useEffect, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NetworkGraph = ({ data, artistName }) => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState(null); // State for popup

  useEffect(() => {
    if (!data || data.length === 0 || !artistName) {
      setGraphData({ nodes: [], links: [] });
      return;
    }

    // Create the central node for the artist
    const nodes = [{ 
      id: artistName, // Use artist name as unique ID
      name: artistName, 
      val: 10, // Make the central node larger
      color: 'lightblue' // Distinguish central node
    }];
    const links = [];

    // Create nodes and links for connected entities
    data.forEach((connection, index) => {
      const targetId = `${connection.connected_entity_name}_${index}`; // Ensure unique ID if names repeat
      nodes.push({
        id: targetId,
        name: connection.connected_entity_name,
        val: 3, // Smaller size for peripheral nodes
        color: 'lightgrey',
        details: connection // Store all connection details on the node
      });
      links.push({
        source: artistName, // Link from artist
        target: targetId, // Link to connected entity
        // We can add details to the link later for tooltips/popups
        relationship: connection.relationship_summary, 
        duration: connection.relationship_duration
      });
    });

    setGraphData({ nodes, links });

  }, [data, artistName]); // Re-run effect if data or artistName changes

  // Function to draw nodes and labels
  const handleNodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const label = node.name;
    const fontSize = 12 / globalScale; // Adjust font size based on zoom
    ctx.font = `${fontSize}px Sans-Serif`;
    const textWidth = ctx.measureText(label).width;
    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4); // Box padding

    // Draw background rectangle for label (optional, for better readability)
    // ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    // ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

    // Draw the node circle with static size (radius = node.val)
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false); // Use node.val directly for radius
    ctx.fillStyle = node.color || 'grey'; // Use node color or default
    ctx.fill();

    // Draw label text, positioned relative to static node size
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'black'; // Label color
    ctx.fillText(label, node.x, node.y + node.val + fontSize); // Position label below node using static radius
  }, []);

  // Handle node click for popup
  const handleNodeClick = (node) => {
    setSelectedNode(node); // Set selected node data for popup
  };

  // Close popup
  const closePopup = () => {
    setSelectedNode(null);
  };

  // Popup styles (basic inline example)
  const popupStyle = {
    position: 'absolute',
    top: '10px',
    right: '10px',
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '5px',
    padding: '15px',
    maxWidth: '300px',
    maxHeight: '80vh', // Prevent popup from being too tall
    overflowY: 'auto', // Add scroll if content exceeds height
    zIndex: 1000, // Ensure popup is above the graph
    boxShadow: '0 2px 10px rgba(0,0,0,0.2)'
  };

  return (
    <div style={{ position: 'relative', border: '1px solid #ccc', margin: '10px 0', width: '100%', height: '600px' }}> {/* Added relative positioning and height */}
      <ForceGraph2D
        graphData={graphData}
        //nodeLabel="name" // Disable default hover label
        nodeAutoColorBy="color"
        nodeCanvasObject={handleNodeCanvasObject} // Use custom drawing
        nodeVal="val" // Use 'val' for node size
        linkDirectionalParticles={1}
        linkDirectionalParticleWidth={2}
        onNodeClick={handleNodeClick} // Use updated click handler
        width={window.innerWidth * 0.9} // Approximate width
        height={600} // Set explicit height
        // Center graph initially might need refinement if container size changes
        // centerAt={...} 
        // zoom={...}
      />

      {/* Popup Section */}
      {selectedNode && (
        <div style={popupStyle}>
          <button 
            onClick={closePopup} 
            style={{ 
              position: 'absolute', 
              top: '5px', 
              right: '5px', 
              background: 'none', 
              border: 'none', 
              fontSize: '1.2em', 
              cursor: 'pointer' 
            }}
          >
            &times; {/* Close icon */}
          </button>
          <h3>{selectedNode.name}</h3>
          {selectedNode.details ? (
            <>
              <p><strong>Type:</strong> {selectedNode.details.entity_type}</p>
              <p><strong>Connection:</strong> {selectedNode.details.relationship_summary}</p>
              <p><strong>Duration:</strong> {selectedNode.details.relationship_duration}</p>
              {selectedNode.details.source_url && (
                <p><strong>Source:</strong> <a href={selectedNode.details.source_url} target="_blank" rel="noopener noreferrer">Link</a></p>
              )}
            </>
          ) : (
             // Handle case for the central artist node which might not have 'details'
             <p>This is the main artist.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default NetworkGraph;
