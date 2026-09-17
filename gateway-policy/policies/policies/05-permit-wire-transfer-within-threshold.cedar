// Baseline permit for routine wire transfers: a genuine positive amount at
// or below the threshold. The lower bound matters — without it, a negative
// amount would satisfy "<= 1000" and be permitted by accident.
permit (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"SendWireTransfer",
    resource is CellGuard::Tool
) when {
    context.amount > 0 && context.amount <= 1000
};
