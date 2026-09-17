// Baseline permit for the routine case: an agent may approve a reimbursement
// that's a genuine positive amount at or below the threshold. The lower
// bound matters — without it, a negative amount would satisfy "<= 500" and
// be permitted by accident. The forbid above always takes precedence over
// this permit regardless.
permit (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"ApproveExpense",
    resource is CellGuard::Tool
) when {
    context.amount > 0 && context.amount <= 500
};
