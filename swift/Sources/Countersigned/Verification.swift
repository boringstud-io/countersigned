import Foundation
import CryptoKit

/// A device that may countersign — `spec/PROTOCOL.md` §8.
public struct Device: Equatable, Sendable {
    public let deviceId: String
    /// base64 of the uncompressed SEC1 point.
    public let pubkey: String
    public let role: String
    public let name: String

    public init(deviceId: String, pubkey: String, role: String = "", name: String = "") {
        self.deviceId = deviceId
        self.pubkey = pubkey
        self.role = role
        self.name = name
    }
}

/// Devices, roles and consumed nonces of one workspace.
public struct Registry: Sendable {
    public var devices: [Device]
    /// role -> action types this role may approve
    public var roles: [String: [String]]
    public var usedNonces: Set<String>
    /// device id -> pubkey as last seen. A changed key means replacement or
    /// restore and invalidates until a human confirms.
    public var knownKeys: [String: String]

    public init(devices: [Device] = [], roles: [String: [String]] = [:],
                usedNonces: Set<String> = [], knownKeys: [String: String] = [:]) {
        self.devices = devices
        self.roles = roles
        self.usedNonces = usedNonces
        self.knownKeys = knownKeys
    }

    public func device(_ id: String) -> Device? {
        devices.first { $0.deviceId == id }
    }
}

public struct Verdict: Equatable, Sendable {
    public let device: Device
    public let version: CanonicalVersion
}

/// A refusal with exactly one reason. The reason is the product: "invalid" alone
/// tells nobody what to do next.
public enum VerificationError: Error, Equatable {
    case wrongWorkspace(claimed: String, expected: String)
    case wrongAction(claimed: String, expected: String)
    case statusNotSignable(String)
    case unknownDevice(String)
    case deviceKeyChanged(String)
    case malformedKeyOrSignature
    case signatureDoesNotVerify
    case unknownRole(String)
    case roleMayNotApprove(role: String, type: String)
    case replay(nonce: String)
}

public enum Verifier {
    /// Newest first — the first version that verifies wins.
    public static let acceptedVersions: [CanonicalVersion] = [.v4, .v3]

    /// Check an approval — `spec/PROTOCOL.md` §6.
    ///
    /// `workspace` and `actionId` are what the *caller* is verifying for, not what
    /// the approval claims. They are checked first, and they must be passed:
    /// a signature only proves that someone signed that payload, never that the
    /// payload belongs here. Omitting this check let an approval from another
    /// workspace verify happily — found on 2026-09-06, before this package had a user.
    public static func verify(action: Action, approval: Approval, registry: Registry,
                              workspace: String, actionId: String,
                              protocolName: String = "nino-go",
                              versions: [CanonicalVersion] = acceptedVersions) throws -> Verdict {
        guard approval.workspace == workspace else {
            throw VerificationError.wrongWorkspace(claimed: approval.workspace, expected: workspace)
        }
        guard approval.actionId == actionId else {
            throw VerificationError.wrongAction(claimed: approval.actionId, expected: actionId)
        }
        guard approval.status == "approved" || approval.status == "rejected" else {
            throw VerificationError.statusNotSignable(approval.status)
        }
        guard let device = registry.device(approval.deviceId) else {
            throw VerificationError.unknownDevice(approval.deviceId)
        }
        if let seen = registry.knownKeys[device.deviceId], seen != device.pubkey {
            throw VerificationError.deviceKeyChanged(device.deviceId)
        }
        guard let pointData = Data(base64Encoded: device.pubkey),
              let key = try? P256.Signing.PublicKey(x963Representation: pointData),
              let signatureData = Data(base64Encoded: approval.signature),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData)
        else {
            throw VerificationError.malformedKeyOrSignature
        }

        var matched: CanonicalVersion?
        for version in versions {
            guard action.digest(version) == approval.digest,
                  let payload = try? approval.payload(version, protocolName: protocolName)
            else { continue }
            if key.isValidSignature(signature, for: payload) {
                matched = version
                break
            }
        }
        guard let version = matched else { throw VerificationError.signatureDoesNotVerify }

        guard let allowed = registry.roles[device.role] else {
            throw VerificationError.unknownRole(device.role)
        }
        guard allowed.contains(action.type) else {
            throw VerificationError.roleMayNotApprove(role: device.role, type: action.type)
        }
        guard !registry.usedNonces.contains(approval.nonce) else {
            throw VerificationError.replay(nonce: approval.nonce)
        }
        return Verdict(device: device, version: version)
    }

    /// Check a raw payload against a key — without the action's content.
    /// Used for production vectors, where the body stays private.
    public static func verifyPayload(_ payload: Data, signature base64Signature: String,
                                     pubkey base64Key: String) -> Bool {
        guard let pointData = Data(base64Encoded: base64Key),
              let key = try? P256.Signing.PublicKey(x963Representation: pointData),
              let signatureData = Data(base64Encoded: base64Signature),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData)
        else { return false }
        return key.isValidSignature(signature, for: payload)
    }
}
