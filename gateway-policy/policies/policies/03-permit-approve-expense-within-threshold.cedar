// Baseline permit for the routine case: an agent may approve a reimbursement
// at or below the threshold. The forbid above always takes precedence.
permit (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"ApproveExpense",
    resource is CellGuard::Tool
) when {
    context.amount <= 500
};
