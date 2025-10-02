export const artworkSearch = async({
                                       artistName,
                                       artworkTitle,
                                       scope,
                                       setIsLoading,
                                       setLoadingTime,
                                       timerRef,
                                       setTimelineData,
                                       setNetworkData,
                                       setError,
                                       setActiveTimelineScope,
                                       setGenreResult,
                                       setArtworkTitle
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
            `http://localhost:8080/api/agent/?artistName=${artistName}&context=${scope}&artworkTitle=${artworkTitle}`
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