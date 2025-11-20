package com.example;

import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.ContentCachingResponseWrapper;

import jakarta.servlet.AsyncEvent;
import jakarta.servlet.AsyncListener;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Optional;

@Component
public class ArtworkCacheFilter extends OncePerRequestFilter {

    private final SqliteHttpCache httpCache =
        new SqliteHttpCache(System.getenv().getOrDefault("ARTIST_HTTP_CACHE_DB", "artist_http_cache.db"));

    /** Returns true if this is a request to /api/agent that contains an artwork title */
    private static boolean isArtworkRequest(HttpServletRequest request){
        String qStr = request.getQueryString();
        return isCacheablePath(request) && qStr.contains("artworkTitle");
    }

    /** Only cache GET /api/agent */
    private static boolean isCacheablePath(HttpServletRequest req) {
        if (!"GET".equalsIgnoreCase(req.getMethod())) return false;
        String p = req.getRequestURI();
        return "/api/agent".equals(p);
    }

    /** Let requests bypass cache if caller sets X-Bypass-Cache: 1 (used for background refresh) */
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if ("1".equals(request.getHeader("X-Bypass-Cache"))) return true;
        return !isCacheablePath(request);
    }

    /** TTLs: per-scope for artwork; fixed for agent */
    private static int[] ttlsForArtworkScope(String scope) {
        String s = scope == null ? "political-events" : scope.toLowerCase();
        if (s.equals("art-movements"))  return new int[]{7*86400, 21*86400};
        if (s.equals("artist-network")) return new int[]{14*86400, 30*86400};
        return new int[]{2*86400, 7*86400}; // political/economic default
    }
    private static int[] ttlsForAgent() {
        return new int[]{14*86400, 30*86400};
    }

    /** Stable keys for both endpoints */
    private static String slug(String s) {
        return s == null ? "" : s.toLowerCase().trim().replaceAll("\\s+","-");
    }
    private static String stableContext(String ctxRaw) {
        if (ctxRaw == null || ctxRaw.isBlank()) return "[]";
        String[] parts = ctxRaw.split(",");
        java.util.List<String> list = new java.util.ArrayList<>();
        for (String p : parts) {
            String t = p.trim().toLowerCase();
            if (!t.isEmpty()) list.add(t);
        }
        java.util.Collections.sort(list);
        return String.join(",", list);
    }
    private static String keyFor(HttpServletRequest req) {
        if (isArtworkRequest(req)) {
            String artist  = req.getParameter("artistName");
            String scope = Optional.ofNullable(req.getParameter("context")).orElse("political-events");
            String title = req.getParameter("artworkTitle");
            return "artist-http-cache:v1:/api/artwork:" + slug(artist) + ":" + scope + ":" + slug(title);
        } else { // /api/agent
            String artist  = req.getParameter("artistName");
            String context = stableContext(req.getParameter("context"));
            return "artist-http-cache:v1:/api/agent:" + slug(artist) + ":" + context;
        }
    }

    /** CORS headers */
    private static void setCors(HttpServletRequest req, HttpServletResponse resp) {
        String origin = Optional.ofNullable(req.getHeader("Origin")).orElse("*");
        resp.setHeader("Access-Control-Allow-Origin", origin);
        resp.setHeader("Vary", "Origin");
        resp.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
        resp.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bypass-Cache");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain)
            throws ServletException, IOException {
        // Assumes we're only running on cacheable things 

        // Handle OPTIONS preflight
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            setCors(request, response);
            response.setStatus(HttpServletResponse.SC_NO_CONTENT);
            return;
        }

        final String key  = keyFor(request);
        System.out.println("Filter: Searching for key " + key);

        var rowOpt = httpCache.get(key);
        if (rowOpt.isPresent()) {
            System.out.println("Filter: Getting something from cache");
            var row = rowOpt.get();
            boolean fresh = System.currentTimeMillis() < row.freshUntil();
            if(fresh){
                System.out.println("Filter: retrieving something from cache");
                response.setHeader("X-Cache", "HIT");
                setCors(request, response);                // add CORS headers
                writeResponse(response, row.body());
                return;
            }

            // if (!fresh) {
            //     System.out.println("Filter: Not fresh and needs to update");
            //     httpCache.refreshAsync(() -> {
            //         try {
            //             String refreshUrl = request.getRequestURL().toString();
            //             String qs = request.getQueryString();
            //             if (qs != null && !qs.isBlank()) refreshUrl += "?" + qs;

            //             var rt = new RestTemplate();
            //             var headers = new org.springframework.http.HttpHeaders();
            //             headers.add("X-Bypass-Cache", "1");
            //             var entity = new org.springframework.http.HttpEntity<String>(headers);
            //             var result = rt.exchange(refreshUrl, org.springframework.http.HttpMethod.GET, entity, String.class);

            //             String body = result.getBody() == null ? "" : result.getBody();
            //             int[] t = isArtworkRequest(request) ? ttlsForAgent()
            //                                                 : ttlsForArtworkScope(Optional.ofNullable(request.getParameter("scope")).orElse("political-events"));
            //             httpCache.put(key, body, t[0], t[1]);
            //         } catch (Exception ignore) {}
            //     });
            // }
            // return;
        }

        // cache MISS or is stale: capture the body and store after controller runs
        System.out.println("Filter: (initial request) dispatching");
        CopyContentWrapper wrapped = new CopyContentWrapper(response);
        filterChain.doFilter(request, wrapped);
        if(request.isAsyncStarted()){
            request.getAsyncContext().addListener(new AsyncListener() {
                public void onComplete(AsyncEvent asyncEvent) throws IOException {
                    System.out.println("Filter: completed stream and caching response now");
                    // Get body that was sent (includes all messages streamed)
                    byte[] bytes = wrapped.getContentAsByteArray();
                    String charsetName = wrapped.getCharacterEncoding() != null
                            ? wrapped.getCharacterEncoding() : StandardCharsets.UTF_8.name();
                    String body = new String(bytes, Charset.forName(charsetName));

                    // Add the last message to the cache
                    if(wrapped.getStatus() == 200){
                        // Get last message that was sent in body - this will contain the final JSON 
                        // response and an additional :flush message
                        int lastDataStart = body.lastIndexOf("data:{\"status\": \"complete\",");
                        if(lastDataStart >= 0){
                            String lastMessage = body.substring(lastDataStart);
                            int[] t = isArtworkRequest(request) ? ttlsForAgent()
                                                                : ttlsForArtworkScope(Optional.ofNullable(request.getParameter("scope")).orElse("political-events"));
                            httpCache.put(key, lastMessage, t[0], t[1]);
                            System.out.println("Filter: added last message to " + key);
                        }
                    }
                    response.setHeader("X-Cache", "MISS");
                    setCors(request, response);
                }

                public void onTimeout(AsyncEvent asyncEvent) throws IOException {}
                public void onError(AsyncEvent asyncEvent) throws IOException {}
                public void onStartAsync(AsyncEvent asyncEvent) throws IOException {}
            });
        }
    }

    private static void writeResponse(HttpServletResponse response, String body) throws IOException {
        response.setStatus(200);
        response.setContentType("text/event-stream");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(body);
    }
}
