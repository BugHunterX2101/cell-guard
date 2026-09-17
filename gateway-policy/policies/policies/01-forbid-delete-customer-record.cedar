// Deleting a customer record is never allowed in this demo — unconditional forbid.
// Cedar semantics: an explicit forbid always wins over any permit, regardless of
// policy evaluation order, so this cannot be overridden by another policy.
forbid (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"DeleteCustomerRecord",
    resource is CellGuard::Tool
);
