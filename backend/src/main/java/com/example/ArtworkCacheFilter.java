package com.example;

import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.ContentCachingResponseWrapper;

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

    /** Only cache GET /api/artwork and GET /api/agent */
    private static boolean isCacheablePath(HttpServletRequest req) {
        if (!"GET".equalsIgnoreCase(req.getMethod())) return false;
        String p = req.getRequestURI();
        return "/api/artwork".equals(p) || "/api/agent".equals(p);
    }

    /** Let requests bypass cache if caller sets X-Bypass-Cache: 1 (used for background refresh) */
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if ("1".equals(request.getHeader("X-Bypass-Cache"))) return true;
        return !isCacheablePath(request);
    }

    /** Which paths can be served directly from cache (short-circuit) */
    private static boolean canShortCircuit(HttpServletRequest req) {
        String path = req.getRequestURI();
        if ("/api/agent".equals(path)) return true; // safe to serve from cache
        if ("/api/artwork".equals(path)) {
            String scope = Optional.ofNullable(req.getParameter("scope")).orElse("political-events");
            // DO NOT short-circuit political-events because summarize() needs controller’s in-memory map.
            return scope.equals("art-movements") || scope.equals("artist-network");
        }
        return false;
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
        String path = req.getRequestURI();
        if ("/api/artwork".equals(path)) {
            String name  = req.getParameter("name");
            String scope = Optional.ofNullable(req.getParameter("scope")).orElse("political-events");
            return "artist-http-cache:v1:/api/artwork:" + scope + ":" + slug(name);
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

        // Handle OPTIONS preflight
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            setCors(request, response);
            response.setStatus(HttpServletResponse.SC_NO_CONTENT);
            return;
        }

        final String path = request.getRequestURI();
        final String key  = keyFor(request);
        final boolean shortCircuit = canShortCircuit(request);

        if (shortCircuit) {
            var rowOpt = httpCache.get(key);
            if (rowOpt.isPresent()) {
                var row = rowOpt.get();
                boolean fresh = System.currentTimeMillis() < row.freshUntil();
                response.setHeader("X-Cache", "HIT");
                setCors(request, response);                // add CORS headers
                writeJson(response, row.body());

                if (!fresh) {
                    httpCache.refreshAsync(() -> {
                        try {
                            String refreshUrl = request.getRequestURL().toString();
                            String qs = request.getQueryString();
                            if (qs != null && !qs.isBlank()) refreshUrl += "?" + qs;

                            var rt = new RestTemplate();
                            var headers = new org.springframework.http.HttpHeaders();
                            headers.add("X-Bypass-Cache", "1");
                            var entity = new org.springframework.http.HttpEntity<String>(headers);
                            var result = rt.exchange(refreshUrl, org.springframework.http.HttpMethod.GET, entity, String.class);

                            String body = result.getBody() == null ? "" : result.getBody();
                            int[] t = "/api/agent".equals(path) ? ttlsForAgent()
                                                                : ttlsForArtworkScope(Optional.ofNullable(request.getParameter("scope")).orElse("political-events"));
                            httpCache.put(key, body, t[0], t[1]);
                        } catch (Exception ignore) {}
                    });
                }
                return;
            }
        }

        // MISS or write-through (political-events): capture the body and store after controller runs
        ContentCachingResponseWrapper wrapped = new ContentCachingResponseWrapper(response);
        try {
            filterChain.doFilter(request, wrapped);
        } finally {
            byte[] bytes = wrapped.getContentAsByteArray();
            String charsetName = wrapped.getCharacterEncoding() != null
                    ? wrapped.getCharacterEncoding() : StandardCharsets.UTF_8.name();
            String body = new String(bytes, Charset.forName(charsetName));

            String ct = wrapped.getContentType();
            if (wrapped.getStatus() == 200 && ct != null && ct.contains("application/json")) {
                int[] t = "/api/agent".equals(path) ? ttlsForAgent()
                        : ttlsForArtworkScope(Optional.ofNullable(request.getParameter("scope")).orElse("political-events"));
                httpCache.put(key, body, t[0], t[1]);
            }
            response.setHeader("X-Cache", "MISS");
            setCors(request, response);
            wrapped.copyBodyToResponse();
        }
    }

    private static void writeJson(HttpServletResponse response, String body) throws IOException {
        response.setStatus(200);
        response.setContentType("application/json");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(body);
    }
}
