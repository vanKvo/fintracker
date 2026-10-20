package com.fintracker.ledger.transaction.service;

import com.fintracker.ledger.category.model.Category;
import com.fintracker.ledger.transaction.model.Transaction;
import org.mockito.invocation.InvocationOnMock;

import java.util.List;
import java.util.UUID;

/** Fixed SYSTEM categories and repository answers for unit tests of statement ingest. */
public final class TestCategories {

    public static final Category GROCERIES = new Category(UUID.randomUUID(), "groceries",
            Category.Level.SYSTEM, null, "groceries", true);
    public static final Category UNCATEGORIZED = new Category(UUID.randomUUID(), "uncategorized",
            Category.Level.SYSTEM, null, "uncategorized", true);

    private TestCategories() {
    }

    public static IngestCatalog catalog() {
        return IngestCatalog.of(List.of(GROCERIES, UNCATEGORIZED));
    }

    /** Answer for bulkInsertReturningFingerprints: every row passed in was newly inserted. */
    @SuppressWarnings("unchecked")
    public static List<String> allInserted(InvocationOnMock invocation) {
        return ((List<Transaction>) invocation.getArgument(1)).stream()
                .map(Transaction::rowFingerprint)
                .toList();
    }
}
