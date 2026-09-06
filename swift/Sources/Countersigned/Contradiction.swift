import Foundation

/// Contradiction detection — `spec/PROTOCOL.md` §7.
///
/// Signatures prove that an action was approved. They cannot prove that nothing
/// else happened. This pass compares the records, the send log and the approvals,
/// and reports where they disagree. It found the real incident of 2026-08-25,
/// when a message went out that had been rejected: the system did not prevent it,
/// it noticed. Both halves matter, and only this one is cheap.
public enum Contradiction: String, Sendable, CaseIterable {
    case rejectedButSent, undecidedButSent, inSendLogWithoutApproval
    case sentWithoutProof, approvedButNotExecuted

    /// Incidents are things that happened and should not have. The rest are
    /// warnings: something is late or missing, but nothing left without cover.
    public var isIncident: Bool {
        switch self {
        case .rejectedButSent, .undecidedButSent, .inSendLogWithoutApproval: true
        case .sentWithoutProof, .approvedButNotExecuted: false
        }
    }

    public func message(when: String) -> String {
        switch self {
        case .rejectedButSent: "Rejected — but it was sent on \(when)"
        case .undecidedButSent: "Not decided yet — but it was sent on \(when)"
        case .inSendLogWithoutApproval:
            "The send log shows a send on \(when) — but this action is not approved"
        case .sentWithoutProof: "Sent on \(when) without a verifiable approval"
        case .approvedButNotExecuted:
            "Approved on \(when) — the executor has not picked it up"
        }
    }
}

/// What the detector needs to know about an action. Deliberately minimal: an
/// implementation maps its own records onto this.
public struct ActionRecord: Equatable, Sendable {
    public let actionId: String
    public let status: String
    public let sentAt: String?
    public let hasValidSignature: Bool
    public let approvedAt: String?

    public init(actionId: String, status: String, sentAt: String? = nil,
                hasValidSignature: Bool = false, approvedAt: String? = nil) {
        self.actionId = actionId
        self.status = status
        self.sentAt = sentAt
        self.hasValidSignature = hasValidSignature
        self.approvedAt = approvedAt
    }
}

public struct Finding: Equatable, Sendable {
    public let actionId: String
    public let cause: Contradiction
    public let when: String

    public var isIncident: Bool { cause.isIncident }
}

public enum ContradictionDetector {
    /// With fewer sources the pass reports less, never more.
    public static func find(actions: [ActionRecord],
                            sendLog: [String: String] = [:],
                            executed: Set<String> = []) -> [Finding] {
        var findings: [Finding] = []
        for action in actions {
            let sentAt = action.sentAt ?? sendLog[action.actionId]
            if let sentAt {
                if action.status == "rejected" {
                    findings.append(Finding(actionId: action.actionId,
                                            cause: .rejectedButSent, when: sentAt))
                } else if action.status != "approved" {
                    findings.append(Finding(actionId: action.actionId,
                                            cause: .undecidedButSent, when: sentAt))
                } else if !action.hasValidSignature {
                    findings.append(Finding(actionId: action.actionId,
                                            cause: .sentWithoutProof, when: sentAt))
                }
            } else if action.status == "approved", !executed.contains(action.actionId),
                      let approvedAt = action.approvedAt {
                findings.append(Finding(actionId: action.actionId,
                                        cause: .approvedButNotExecuted, when: approvedAt))
            }
        }
        let known = Set(actions.map(\.actionId))
        let approved = Set(actions.filter { $0.status == "approved" }.map(\.actionId))
        for (actionId, when) in sendLog.sorted(by: { $0.key < $1.key })
        where !known.contains(actionId) || !approved.contains(actionId) {
            if !findings.contains(where: { $0.actionId == actionId }) {
                findings.append(Finding(actionId: actionId,
                                        cause: .inSendLogWithoutApproval, when: when))
            }
        }
        return findings
    }
}
