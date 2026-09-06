import Testing
@testable import Countersigned

/// Contradiction detection — `spec/PROTOCOL.md` §7.
struct ContradictionTests {

    /// The real case of 2026-08-25.
    @Test func rejectedButSentIsAnIncident() {
        let findings = ContradictionDetector.find(actions: [
            ActionRecord(actionId: "act-1", status: "rejected", sentAt: "2026-08-25T09:00:00Z")])
        #expect(findings.map(\.cause) == [.rejectedButSent])
        #expect(findings[0].isIncident)
    }

    @Test func sentWhileUndecidedIsAnIncident() {
        let findings = ContradictionDetector.find(actions: [
            ActionRecord(actionId: "act-2", status: "open", sentAt: "2026-08-29T09:00:00Z")])
        #expect(findings[0].cause == .undecidedButSent)
    }

    /// Approved and sent, but no signature verifies today — worth showing, and
    /// not the same as sending against a decision.
    @Test func sentWithoutProofIsAWarning() {
        let findings = ContradictionDetector.find(actions: [
            ActionRecord(actionId: "act-3", status: "approved", sentAt: "2026-08-18T09:00:00Z",
                         hasValidSignature: false)])
        #expect(findings[0].cause == .sentWithoutProof)
        #expect(!findings[0].isIncident)
    }

    @Test func sendLogEntryWithoutAnyAction() {
        let findings = ContradictionDetector.find(
            actions: [], sendLog: ["act-ghost": "2026-09-01T10:00:00Z"])
        #expect(findings[0].cause == .inSendLogWithoutApproval)
        #expect(findings[0].isIncident)
    }

    @Test func approvedAndSentWithProofIsSilent() {
        let findings = ContradictionDetector.find(actions: [
            ActionRecord(actionId: "act-4", status: "approved", sentAt: "2026-09-01T10:00:00Z",
                         hasValidSignature: true)])
        #expect(findings.isEmpty)
    }

    @Test func approvedButNeverExecutedIsAWarning() {
        let findings = ContradictionDetector.find(
            actions: [ActionRecord(actionId: "act-5", status: "approved",
                                   approvedAt: "2026-09-01T10:00:00Z")],
            executed: [])
        #expect(findings[0].cause == .approvedButNotExecuted)
        #expect(!findings[0].isIncident)
    }
}
