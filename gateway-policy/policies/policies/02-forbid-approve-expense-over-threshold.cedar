// Reimbursements above the fixed threshold are forbidden regardless of who is
// asking or what text convinced the agent to attempt it — the check is on the
// actual parameter value in context, not on anything the model was told.
forbid (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"ApproveExpense",
    resource is CellGuard::Tool
) when {
    context.amount > 500
};
