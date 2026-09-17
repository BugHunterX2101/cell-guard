// Baseline permit for routine wire transfers at or below the threshold.
permit (
    principal is CellGuard::Agent,
    action == CellGuard::Action::"SendWireTransfer",
    resource is CellGuard::Tool
) when {
    context.amount <= 1000
};
