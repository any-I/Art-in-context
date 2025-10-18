// Scope information
const scopeInfo = {
    "political-events": "timelineEvents",
    "art-movements": "timelineEvents",
    "artist-network": "networkData",
    "personal-events": "timelineEvents",
    "economic-events": "timelineEvents",
    "genre": "timelineEvents",
    "medium": "timelineEvents"
};

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

// Takes timeline events returned by backend and maps them to the appropriate format, also chronologically
// sorting them
const getTransformedTimelineEvents = (data) => {
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
    return transformedData;
}

// Main function used to perform search and handle results
export const performSearch = async (  searchParams,
                                      setIsLoading,
                                      setLoadingTime,
                                      timerRef,
                                      setTimelineData,
                                      setNetworkData,
                                      setError,
                                      setActiveTimelineScope
                                  ) => {
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

    try {
        // Check that required scope and artistName keys are in searchParams
        // and throw if not
        if(!("scope" in searchParams) || !("artistName" in searchParams) ||
            searchParams["scope"] === "" || searchParams["artistName"] === ""){
            throw new Error("Expected scope and artist name to be defined in search");
        }

        // Extract parameters and construct search url
        const scope = searchParams.scope;
        const artistName = searchParams.artistName;
        const baseUrl =
              process.env.NODE_ENV === "production"
            ? "https://art-in-context.onrender.com"
            : "http://localhost:8080";
        console.log(baseUrl);
        let searchUrl = `${baseUrl}/api/agent?artistName=${artistName}&context=${scope}`;

        if("artworkTitle" in searchParams){
            searchUrl += "&artworkTitle=" + searchParams.artworkTitle;
        }

        // Fetch response from backend
        const response = await fetch(searchUrl);
        if (!response.ok) throw new Error("Error performing AI search");
        const data = await response.json();

        // Handle error on backend
        if (data.error) {
            throw new Error(data.error);
        }

        // Parse network/timeline data from response depending on scope
        else if (scope in scopeInfo && scopeInfo[scope] in data){
            const dataKey = scopeInfo[scope];
            console.log(`Received ${dataKey} for scope: ${scope}`, data[dataKey]);

            //handling timeline events data
            if(dataKey === "timelineEvents"){
                const transformedData = getTransformedTimelineEvents(data);
                console.log("Transformed data: ", transformedData);
                setTimelineData(transformedData);
                setNetworkData([]);
                setActiveTimelineScope(scope);
            }

            //handling network data
            else {
                setNetworkData(data.networkData);
                setTimelineData([]);
            }
        }

        // Handle cases where data is missing for the expected scope
        else {
            console.warn(`Data key ('${scopeInfo[scope]}') not found in response for scope '${scope}'.`);
            throw new Error("Received response, but no valid data found for the selected scope.");
        }
    } catch (err) {
        // Handle all error states - print error message and clear data arrays
        setError(err.message || "Failed to perform AI search");
        setTimelineData([]);
        setNetworkData([]);
    }
    finally {
        setIsLoading(false);
        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }
    }
}
