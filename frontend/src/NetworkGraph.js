import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as d3 from 'd3';

const NetworkGraph = ({ data, artistName }) => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });
  const svgRef = useRef();
  const simulationRef = useRef();

  useEffect(() => {
    if (!data || data.length === 0 || !artistName) {
      setGraphData({ nodes: [], links: [] });
      return;
    }

    const nodes = [{
      id: artistName, 
      name: artistName,
      val: 10, 
      color: 'lightblue', 
      fx: null, 
      fy: null
    }];
    const links = [];

    data.forEach((connection, index) => {
      const targetId = `${connection.connected_entity_name}_${index}`; 
      nodes.push({
        id: targetId,
        name: connection.connected_entity_name,
        val: 3, 
        color: 'lightgrey',
        details: connection, 
        fx: null,
        fy: null
      });
      links.push({
        source: artistName, 
        target: targetId, 
        relationship: connection.relationship_summary,
        duration: connection.relationship_duration
      });
    });

    setGraphData({ nodes, links });

  }, [data, artistName]);

  useEffect(() => {
    if (!graphData.nodes.length) return; 

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous elements

    // Stop previous simulation if it exists
    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    // Create a wrapper group for zoom/pan
    const g = svg.append("g");

    // --- ADDED: Group for the connecting lines ---
    const linkGroup = g.append("g")
        .attr("class", "links")
        .attr("stroke", "#999") // Style for the lines
        .attr("stroke-opacity", 0.6)
        .attr("stroke-width", 1.5);

    // --- ADDED: Fixed node radii ---
    const centralNodeRadius = 25; // Slightly larger radius for the main artist
    const peripheralNodeRadius = 15; // Fixed radius for other nodes

    // --- ADDED: Define scale for link distance based on connection score (inverted) ---
    // Assuming connection_score ranges roughly 1-10. Adjust domain/range as needed.
    // Higher score = shorter distance (stronger connection)
    const distanceScale = d3.scaleLinear()
      .domain([1, 10]) // Expected range of connection_score
      .range([350, 40]); // MODIFIED: Increased range for more exaggeration

    // --- D3 Force Simulation Setup ---
    const simulation = d3.forceSimulation(graphData.nodes)
      // --- MODIFIED: Add forceLink based on connection score ---
      .force("link", d3.forceLink(graphData.links)
                      .id(d => d.id)
                      .distance(l => distanceScale(l.target.details?.connection_score || 1)) // Use target node's score for distance
                      .strength(0.5) // Adjust link strength as needed
      )
      .force("charge", d3.forceManyBody().strength(-150)) // Adjusted charge potentially needed with links
      .force("center", d3.forceCenter(width / 2, height / 2))
      // --- MODIFIED: Collision force based on fixed radii ---
      .force("collide", d3.forceCollide().radius(d => (d.id === artistName ? centralNodeRadius : peripheralNodeRadius) + 5))
      .on("tick", ticked);

    simulationRef.current = simulation; 

    // --- ADDED: Create line elements, binding data from non-central nodes ---
    const lines = linkGroup.selectAll("line")
      .data(graphData.nodes.filter(d => d.id !== artistName)) // Only nodes that are NOT the central one
      .join("line");

    // Append node groups to the wrapper 'g', not 'svg'
    const nodeGroup = g.append("g") 
        .attr("class", "nodes")
      .selectAll("g") 
      .data(graphData.nodes)
      .join("g") 
      ;

    nodeGroup.append("circle")
      // --- MODIFIED: Set radius based on fixed sizes ---
      .attr("r", d => d.id === artistName ? centralNodeRadius : peripheralNodeRadius)
      .attr("fill", d => d.color || 'grey')
      .on("click", (event, d) => {
        const [x, y] = d3.pointer(event, svgRef.current.parentElement); // Use parent for positioning if g is transformed
        setPopupPosition({ x, y });
        handleNodeClick(d); // Trigger popup on click
        event.stopPropagation();
      });

    nodeGroup.append("text")
      .text(d => d.name)
      .attr("x", 0) // Center text horizontally in the group
      // --- MODIFIED: Position text below the circle using fixed radii ---
      .attr("y", d => (d.id === artistName ? centralNodeRadius : peripheralNodeRadius) + 10)
      .attr("text-anchor", "middle") // Center text
      .attr("font-size", "10px")
      .attr("fill", "black");

    // --- Tick Function (updates positions) ---
    function ticked() {
      // --- ADDED: Find central node --- 
      const centralNode = graphData.nodes.find(n => n.id === artistName);

      // Apply node positions
      nodeGroup
        .attr("transform", d => `translate(${d.x},${d.y})`);

      // --- ADDED: Update line positions --- 
      if (centralNode) { // Ensure central node exists
        lines
          .attr("x1", centralNode.x)
          .attr("y1", centralNode.y)
          .attr("x2", d => d.x)
          .attr("y2", d => d.y);
      }
    }

    return () => {
      simulation.stop(); 
    };

  }, [graphData]); // Rerun effect if graphData changes

  const handleNodeClick = (node) => {
    setSelectedNode(node); 
  };

  const closePopup = () => {
    setSelectedNode(null);
  };

  const popupStyle = {
    position: 'absolute',
    left: `${popupPosition.x + 10}px`, 
    top: `${popupPosition.y + 10}px`,  
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '5px',
    padding: '15px',
    maxWidth: '300px',
    maxHeight: '80vh', 
    overflowY: 'auto', 
    zIndex: 1000, 
    boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
    pointerEvents: 'auto' 
  };

  return (
    <div style={{ position: 'relative', border: '1px solid #ccc', margin: '10px 0', width: '100%', height: '600px' }}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>

      {selectedNode && (
        <div style={popupStyle}>
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
             <p>This is the main artist.</p>
          )}
          <button onClick={closePopup} style={{ marginTop: '10px', padding: '5px 10px', cursor: 'pointer' }}>Close</button>
        </div>
      )}
    </div>
  );
};

export default NetworkGraph;
