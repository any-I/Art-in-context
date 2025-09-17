import {OpenStreetMapProvider} from "leaflet-geosearch";

export const geocodeLocations = async ({
    timelineData,
    setMapMarkers
}) => {
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