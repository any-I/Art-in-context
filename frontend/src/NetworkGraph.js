import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as d3 from 'd3';

const NetworkGraph = ({ data, artistName }) => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState(null); 
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 }); 
  const svgRef = useRef(); 
  const simulationRef = useRef(); 
  const wasDraggedRef = useRef(false); // Ref to track drag state during zoom

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
        duration: connection.relationship_duration,
        score: connection.connection_score || 1 // Store score, default to 1 if missing
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

    // --- Fix central node position ---
    const centralNode = graphData.nodes.find(node => node.id === artistName);
    if (centralNode) {
      centralNode.fx = width / 2;
      centralNode.fy = height / 2;
    }

    // Create a wrapper group for zoom/pan
    const g = svg.append("g"); 

    // --- Define scale for node radius ---
    // Use power scale for more exaggeration
    const radiusScale = d3.scalePow().exponent(2) 
      .domain([1, 10]) // Expected range of connection_score
      .range([4, 55]); // Corresponding radius size range (Quadratic scale, adjusted range)
    
    const centralNodeRadius = 60; // Fixed larger radius for the main artist (Increased)

    // --- Define scale for link distance based on score --- 
    // Higher score = shorter distance
    const linkDistanceScale = d3.scaleLinear()
      .domain([1, 10]) // Expected range of connection_score
      .range([400, 40]); // Corresponding distance range (inverted, increased range for exaggeration)

    // --- D3 Force Simulation Setup ---
    const simulation = d3.forceSimulation(graphData.nodes)
      // Use the link data and distance scale
      .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(link => linkDistanceScale(link.score || 1)))
      .force("charge", d3.forceManyBody().strength(-30)) // Slightly weaker repulsion 
      .force("center", d3.forceCenter(width / 2, height / 2))
      // Add collision force based on calculated radius + padding
      .force("collide", d3.forceCollide().radius(d => (d.id === artistName ? centralNodeRadius : radiusScale(d.details?.connection_score || 1)) + 3)) // Use updated scale logic
      .on("tick", ticked);

    simulationRef.current = simulation; 

    // Append links (lines) to the wrapper 'g'
    const linkGroup = g.append("g")
        .attr("class", "links")
        .attr("stroke", "#999") // Default link color
        .attr("stroke-opacity", 0.6)
      .selectAll("line")
      .data(graphData.links)
      .join("line")
        .attr("stroke-width", 1.5); // Default link width

    // Append node groups to the wrapper 'g', not 'svg'
    const nodeGroup = g.append("g") 
        .attr("class", "nodes")
      .selectAll("g") 
      .data(graphData.nodes)
      .join("g") 
      .call(drag(simulation)); 

    nodeGroup.append("circle")
      // Set radius based on score, with a fixed size for the central artist
      .attr("r", d => d.id === artistName ? centralNodeRadius : radiusScale(d.details?.connection_score || 1)) // Use updated scale logic
      .attr("fill", d => d.color || 'grey')
      .on("click", (event, d) => {
        const [x, y] = d3.pointer(event, svgRef.current); 
        setPopupPosition({ x, y }); 
        handleNodeClick(d); // Trigger popup on click
        event.stopPropagation(); 
      });

    nodeGroup.append("text")
      .text(d => d.name)
      .attr("x", 0) // Center text horizontally in the group
      // Position text below the circle using the dynamic radius
      .attr("y", d => (d.id === artistName ? centralNodeRadius : radiusScale(d.details?.connection_score || 1)) + 10) // Use updated scale logic
      .attr("text-anchor", "middle") // Center text
      .attr("font-size", "10px")
      .attr("fill", "black");

    // --- Tick Function (updates positions) ---
    function ticked() {
      // Update link positions
      linkGroup
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);

      // Apply node positions
      nodeGroup
        .attr("transform", d => `translate(${d.x},${d.y})`); 
    }

    // --- Drag Handling (for individual nodes) ---
    function drag(simulation) {
      function dragstarted(event, d) {
        // Only activate simulation and set fx/fy if it's NOT the central node
        if (d.id !== artistName) {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        }
      }

      function dragged(event, d) {
        // Only update fx/fy if it's NOT the central node
        if (d.id !== artistName) {
          d.fx = event.x;
          d.fy = event.y;
        }
      }

      function dragended(event, d) {
        // Only deactivate simulation and clear fx/fy if it's NOT the central node
        if (d.id !== artistName) {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }
      }

      return d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended);
    }

    // --- Zoom Handling (for panning/zooming the whole view) ---
    const zoomed = (event) => {
      // Only apply transform if zoom/pan actually happened
      if (event.sourceEvent && (event.sourceEvent.type === 'mousemove' || event.sourceEvent.type === 'touchmove' || event.sourceEvent.type === 'wheel')) {
        wasDraggedRef.current = true; // Mark as dragged if zooming/panning
        g.attr("transform", event.transform);
      } else if (event.transform) {
        // Handle initial transform or programmatic zoom if needed, might still mark as dragged
        // wasDraggedRef.current = true;
        g.attr("transform", event.transform);
      }
    };

    const zoom = d3.zoom()
      .scaleExtent([0.1, 8]) // Set zoom limits
      .on("start", () => {
        wasDraggedRef.current = false; // Reset drag flag on interaction start
      })
      .on("zoom", zoomed) // Use the modified zoomed function
      .on("end", (event) => {
        // Close popup only if it was a click (no drag) on the background
        if (!wasDraggedRef.current && event.sourceEvent && event.sourceEvent.target === svgRef.current) {
          closePopup();
        }
      });

    // Apply zoom behavior to the SVG element
    svg.call(zoom);

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
    boxShadow: '0 2px 10px rgba(0,0,0,0.2)'
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
        </div>
      )}
    </div>
  );
};

export default NetworkGraph;
