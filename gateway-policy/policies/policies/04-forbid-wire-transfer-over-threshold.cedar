// Wire transfers above the fixed threshold are forbidden — same shape as the
// expense-threshold rule, evaluated on the transfer amount actually attempted.
forbid (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"SendWireTransfer",
    resource is CellGuard::Tool
) when {
    context.amount > 1000
};
