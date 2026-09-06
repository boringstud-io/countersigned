import Foundation

/// What a device asserts when it countersigns an action — `spec/PROTOCOL.md` §5.
public struct Approval: Equatable, Sendable {
    public static let separator = "|"

    /// `owner/repo` — the data space this approval is bound to. Without it, an
    /// approval would be byte-identical against another workspace.
    public let workspace: String
    public let actionId: String
    /// `approved` or `rejected`; nothing else is signable.
    public let status: String
    public let digest: String
    public let nonce: String
    public let at: String
    public let deviceId: String
    /// base64 DER. Empty while building a payload to sign.
    public let signature: String

    public init(workspace: String, actionId: String, status: String, digest: String,
                nonce: String, at: String, deviceId: String, signature: String = "") {
        self.workspace = workspace
        self.actionId = actionId
        self.status = status
        self.digest = digest
        self.nonce = nonce
        self.at = at
        self.deviceId = deviceId
        self.signature = signature
    }

    public enum PayloadError: Error, Equatable {
        /// A field containing the separator would make the payload re-splittable
        /// in more than one way — and a payload that can be re-split can be forged.
        case fieldContainsSeparator(String)
    }

    public func payload(_ version: CanonicalVersion = .v3,
                        protocolName: String = "nino-go") throws -> Data {
        let parts = ["\(protocolName)-v\(version.rawValue)", workspace, actionId,
                     status, digest, nonce, at, deviceId]
        for part in parts where part.contains(Self.separator) {
            throw PayloadError.fieldContainsSeparator(part)
        }
        return Data(parts.joined(separator: Self.separator).utf8)
    }
}
