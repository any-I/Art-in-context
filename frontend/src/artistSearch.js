// TODO do we want the same "scope" paths if user is trying to search for an artwork?

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

export const agentSearch = async ({
                                      artistName,
                                      scope,
                                      setIsLoading,
                                      setLoadingTime,
                                      timerRef,
                                      setTimelineData,
                                      setNetworkData,
                                      setError,
                                      setActiveTimelineScope,
                                      setGenreResult,
                                  }) => {
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