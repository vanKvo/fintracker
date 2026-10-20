package com.fintracker.ledger.transaction.dto;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;
import java.util.UUID;

/**
 * REQ-2.2 "Inline Row Modification" / TXT-01. Every field is optional so a single PATCH can update
 * any subset in one round trip; the controller rejects a request with none set. A type or
 * direction left out keeps its stored value, and the resulting pair must satisfy TXT-01's rule.
 *
 * <p>DP-LEDGER-CATEGORIES-04: {@code categoryId} is the way to recategorize; {@code category} (a
 * display name) is still accepted and resolved to an id. When both are sent, the id wins.
 */
public record UpdateTransactionRequest(
        UUID categoryId,
        @Size(max = 100) String category,
        BigDecimal amount,
        @Pattern(regexp = "EXPENSE|INCOME|REFUND|TRANSFER|ADJUSTMENT") String type,
        @Pattern(regexp = "DEBIT|CREDIT") String direction,
        Boolean isRecurring,
        UUID linkedTransactionId
) {
    public boolean isEmpty() {
        return categoryId == null && category == null && amount == null && type == null && direction == null
                && isRecurring == null && linkedTransactionId == null;
    }
}
