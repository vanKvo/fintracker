package com.fintracker.ledger.testsupport;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.HexFormat;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

import static com.fintracker.ledger.testsupport.AbstractIntegrationTest.POSTGRES;

/**
 * Superuser fixture inserts and lookups for integration tests. Runs outside RLS, so tests can
 * set up and inspect any tenant's rows while the code under test runs as the restricted app_user.
 */
public final class LedgerFixtures {

    private LedgerFixtures() {
    }

    public static Connection superuserConnection() throws SQLException {
        return DriverManager.getConnection(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
    }

    public static UUID insertAccount(UUID owner) throws SQLException {
        var accountId = UUID.randomUUID();
        try (Connection conn = superuserConnection();
             PreparedStatement ps = conn.prepareStatement("""
                     INSERT INTO ledger.accounts (account_id, user_id, account_name, account_type, sync_mode)
                     VALUES (?, ?, 'Test Account', 'CHECKING', 'MANUAL')
                     """)) {
            ps.setObject(1, accountId);
            ps.setObject(2, owner);
            ps.execute();
        }
        return accountId;
    }

    public static UUID insertStatement(UUID accountId) throws SQLException {
        var statementId = UUID.randomUUID();
        try (Connection conn = superuserConnection();
             PreparedStatement ps = conn.prepareStatement("""
                     INSERT INTO ledger.statements
                         (statement_id, account_id, s3_object_key, status, opening_date, closing_date, content_hash)
                     VALUES (?, ?, 'statements/test/stmt.csv', 'PROCESSING', '2026-08-03', '2026-09-02', ?)
                     """)) {
            ps.setObject(1, statementId);
            ps.setObject(2, accountId);
            ps.setObject(3, randomFingerprint());
            ps.execute();
        }
        return statementId;
    }

    public static UUID systemCategoryId(String code) throws SQLException {
        try (Connection conn = superuserConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT category_id FROM ledger.categories WHERE level = 'SYSTEM' AND code = ?")) {
            ps.setString(1, code);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    throw new IllegalStateException("No SYSTEM category with code " + code);
                }
                return rs.getObject(1, UUID.class);
            }
        }
    }

    public static UUID insertUserCategory(UUID owner, String normalizedName, boolean active) throws SQLException {
        var categoryId = UUID.randomUUID();
        try (Connection conn = superuserConnection();
             PreparedStatement ps = conn.prepareStatement("""
                     INSERT INTO ledger.categories (category_id, category_name, level, user_id, is_active)
                     VALUES (?, ?, 'USER', ?, ?)
                     """)) {
            ps.setObject(1, categoryId);
            ps.setString(2, normalizedName);
            ps.setObject(3, owner);
            ps.setBoolean(4, active);
            ps.execute();
        }
        return categoryId;
    }

    public static void deactivateCategory(UUID categoryId) throws SQLException {
        try (Connection conn = superuserConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "UPDATE ledger.categories SET is_active = false WHERE category_id = ?")) {
            ps.setObject(1, categoryId);
            ps.execute();
        }
    }

    public static String randomFingerprint() {
        var bytes = new byte[32];
        ThreadLocalRandom.current().nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }
}
