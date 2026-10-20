package com.fintracker.ledger.transaction.service;

import com.fintracker.ledger.category.repository.CategoryReadRepository;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.UUID;

/** DP-LEDGER-CATEGORIES-04/05: looks up the Ledger categories a transaction may be filed under. */
@Component
public class TransactionCategoryResolver {

    private final CategoryReadRepository categoryReadRepository;

    public TransactionCategoryResolver(CategoryReadRepository categoryReadRepository) {
        this.categoryReadRepository = categoryReadRepository;
    }

    /** One query pair per package, not per row: SYSTEM categories plus the user's own. */
    public IngestCatalog ingestCatalog(UUID userId) {
        var categories = new ArrayList<>(categoryReadRepository.findAllSystem());
        categories.addAll(categoryReadRepository.findAllUserCategories(userId));
        return IngestCatalog.of(categories);
    }
}
