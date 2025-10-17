package com.example;

import java.sql.*;
import java.time.Instant;
import java.util.Optional;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SqliteHttpCache {
    private final String url;
    private final ExecutorService refreshPool = Executors.newFixedThreadPool(2);

    public SqliteHttpCache(String dbPath) {
        this.url = "jdbc:sqlite:" + dbPath;
        init();
    }

    private void init() {
        try (Connection c = DriverManager.getConnection(url); Statement s = c.createStatement()) {
            s.execute("PRAGMA journal_mode=WAL;");
            s.execute("PRAGMA synchronous=NORMAL;");
            s.execute("""
              CREATE TABLE IF NOT EXISTS cache(
                key TEXT PRIMARY KEY,
                body TEXT NOT NULL,
                fresh_until INTEGER NOT NULL,
                stale_until INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
              )
            """);
            s.execute("""
              CREATE TABLE IF NOT EXISTS locks(
                key TEXT PRIMARY KEY,
                locked_at INTEGER NOT NULL
              )
            """);
            s.execute("CREATE INDEX IF NOT EXISTS idx_cache_fresh ON cache(fresh_until)");
            s.execute("CREATE INDEX IF NOT EXISTS idx_cache_stale ON cache(stale_until)");
        } catch (SQLException e) {
            throw new RuntimeException("Failed to init SQLite", e);
        }
    }

    public record Row(String body, long freshUntil, long staleUntil) {}

    public Optional<Row> get(String key) {
        long now = Instant.now().toEpochMilli();
        try (Connection c = DriverManager.getConnection(url);
        PreparedStatement ps = c.prepareStatement("SELECT body,fresh_until,stale_until FROM cache WHERE key=?")) {
            ps.setString(1, key);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) return Optional.empty();
                String body = rs.getString(1);
                long fresh = rs.getLong(2), stale = rs.getLong(3);
                if (now < fresh || now < stale) return Optional.of(new Row(body, fresh, stale));
                return Optional.empty();
            }
        } catch (SQLException e) { throw new RuntimeException(e); }
    }

    public void put(String key, String body, int freshSecs, int staleSecs) {
        long now = Instant.now().toEpochMilli();
        long freshUntil = now + freshSecs * 1000L;
        long staleUntil = now + (freshSecs + staleSecs) * 1000L;
        String sql = """
          INSERT INTO cache(key,body,fresh_until,stale_until,created_at,updated_at)
          VALUES(?,?,?,?,?,?)
          ON CONFLICT(key) DO UPDATE SET
            body=excluded.body,
            fresh_until=excluded.fresh_until,
            stale_until=excluded.stale_until,
            updated_at=excluded.updated_at
        """;
        try (Connection c = DriverManager.getConnection(url);
             PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setString(1, key);
            ps.setString(2, body);
            ps.setLong(3, freshUntil);
            ps.setLong(4, staleUntil);
            ps.setLong(5, now);
            ps.setLong(6, now);
            ps.executeUpdate();
        } catch (SQLException e) { throw new RuntimeException(e); }
    }

    public boolean acquireLock(String key, long ttlMs) {
        long now = Instant.now().toEpochMilli();
        try (Connection c = DriverManager.getConnection(url)) {
            c.setAutoCommit(false);
            try (PreparedStatement ins = c.prepareStatement("INSERT INTO locks(key,locked_at) VALUES(?,?)")) {
                ins.setString(1, key); ins.setLong(2, now); ins.executeUpdate();
                c.commit(); return true;
            } catch (SQLException e) {
                try (PreparedStatement sel = c.prepareStatement("SELECT locked_at FROM locks WHERE key=?")) {
                    sel.setString(1, key);
                    try (ResultSet rs = sel.executeQuery()) {
                        if (rs.next() && now - rs.getLong(1) > ttlMs) {
                            try (PreparedStatement upd = c.prepareStatement("UPDATE locks SET locked_at=? WHERE key=?")) {
                                upd.setLong(1, now); upd.setString(2, key); upd.executeUpdate();
                                c.commit(); return true;
                            }
                        }
                    }
                }
                c.rollback(); return false;
            } finally { c.setAutoCommit(true); }
        } catch (SQLException e) { throw new RuntimeException(e); }
    }

    public void releaseLock(String key) {
        try (Connection c = DriverManager.getConnection(url);
             PreparedStatement ps = c.prepareStatement("DELETE FROM locks WHERE key=?")) {
            ps.setString(1, key); ps.executeUpdate();
        } catch (SQLException ignored) {}
    }

    public void refreshAsync(Runnable r) {
        refreshPool.submit(r);
    }
}
