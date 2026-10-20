package com.fintracker.ledger.transaction.controller;

import com.fintracker.ledger.transaction.dto.AppendTagsRequest;
import com.fintracker.ledger.transaction.dto.BulkActionRequest;
import com.fintracker.ledger.transaction.dto.ManualTransactionRequest;
import com.fintracker.ledger.transaction.dto.SplitTransactionRequest;
import com.fintracker.ledger.transaction.dto.UpdateTransactionRequest;
import com.fintracker.ledger.transaction.model.Transaction;
import com.fintracker.ledger.transaction.model.TransactionFilter;
import com.fintracker.ledger.transaction.service.TransactionService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/ledger/transactions")
public class TransactionController {

    private final TransactionService transactionService;

    public TransactionController(TransactionService transactionService) {
        this.transactionService = transactionService;
    }

    /**
     * REQ-2.2 "Inline Row Modification" business constraint: the category drop-down list, so the
     * UI never invents its own set. DP-LEDGER-CATEGORIES-04: read from the database — the user's
     * active custom categories and the active SYSTEM ones.
     */
    @GetMapping("/categories")
    public ResponseEntity<List<String>> getCategories(@RequestAttribute("userId") UUID userId) {
        return ResponseEntity.ok(transactionService.assignableCategoryNames(userId));
    }

    @GetMapping
    public ResponseEntity<List<Transaction>> getTransactions(
            @RequestAttribute("userId") UUID userId,
            @RequestParam(required = false) UUID accountId,
            @RequestParam(required = false) String merchant,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate dateFrom,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate dateTo,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) List<String> tags,
            @RequestParam(required = false) Transaction.TransactionStatus status,
            @RequestParam(required = false) Transaction.TransactionType type,
            @RequestParam(required = false) Transaction.TransactionDirection direction,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "50") @Min(1) @Max(200) int size
    ) {
        var filter = new TransactionFilter(userId, accountId, merchant, dateFrom, dateTo,
                category, tags, status, type, direction, page, size);
        return ResponseEntity.ok(transactionService.getTransactions(filter));
    }

    /**
     * REQ-2.3.1 "Manual Row Insertion". source/isManual/status are fixed server-side —
     * see TransactionServiceImpl.createManualTransaction.
     */
    @PostMapping
    public ResponseEntity<Transaction> createManualTransaction(
            @Valid @RequestBody ManualTransactionRequest request,
            @RequestAttribute("userId") UUID userId) {
        var created = transactionService.createManualTransaction(request, userId);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/{id}/approve")
    public ResponseEntity<Void> approveTransaction(@PathVariable UUID id,
                                                   @RequestAttribute("userId") UUID userId) {
        transactionService.approveTransaction(id, userId);
        return ResponseEntity.noContent().build();
    }

    @PatchMapping("/{id}")
    public ResponseEntity<Void> updateTransaction(@PathVariable UUID id,
                                                  @Valid @RequestBody UpdateTransactionRequest request,
                                                  @RequestAttribute("userId") UUID userId) {
        if (request.isEmpty()) {
            throw new IllegalArgumentException("At least one field to update must be provided.");
        }
        if (request.categoryId() != null) {
            transactionService.recategorize(id, request.categoryId(), userId);
        } else if (request.category() != null) {
            transactionService.updateCategory(id, request.category(), userId);
        }
        if (request.amount() != null) {
            transactionService.updateAmount(id, request.amount(), userId);
        }
        if (request.type() != null || request.direction() != null) {
            transactionService.updateTypeAndDirection(id, request.type(), request.direction(), userId);
        }
        if (request.isRecurring() != null) {
            transactionService.updateRecurring(id, request.isRecurring(), userId);
        }
        if (request.linkedTransactionId() != null) {
            transactionService.linkTransaction(id, request.linkedTransactionId(), userId);
        }
        return ResponseEntity.noContent().build();
    }

    @PutMapping("/{id}/exclude")
    public ResponseEntity<Void> toggleExclude(@PathVariable UUID id,
                                               @RequestParam boolean exclude,
                                               @RequestAttribute("userId") UUID userId) {
        transactionService.toggleExclude(id, exclude, userId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/split")
    public ResponseEntity<List<Transaction>> splitTransaction(
            @PathVariable UUID id,
            @Valid @RequestBody SplitTransactionRequest request,
            @RequestAttribute("userId") UUID userId
    ) {
        var splitRequests = request.splits().stream()
                .map(s -> new TransactionService.SplitRequest(s.amount(), s.category()))
                .toList();
        return ResponseEntity.ok(transactionService.splitTransaction(id, splitRequests, userId));
    }

    @PatchMapping("/{id}/tags")
    public ResponseEntity<Void> appendTags(@PathVariable UUID id,
                                           @Valid @RequestBody AppendTagsRequest request,
                                           @RequestAttribute("userId") UUID userId) {
        transactionService.appendTags(id, request.tags(), userId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/bulk")
    public ResponseEntity<Void> bulkAction(@Valid @RequestBody BulkActionRequest request,
                                           @RequestAttribute("userId") UUID userId) {
        switch (request.action()) {
            case APPROVE -> transactionService.bulkApprove(request.transactionIds(), userId);
            case EXCLUDE -> request.transactionIds().forEach(id -> transactionService.toggleExclude(id, true, userId));
            case INCLUDE -> request.transactionIds().forEach(id -> transactionService.toggleExclude(id, false, userId));
        }
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteTransaction(@PathVariable UUID id,
                                                  @RequestAttribute("userId") UUID userId) {
        transactionService.deleteManualTransaction(id, userId);
        return ResponseEntity.noContent().build();
    }
}
