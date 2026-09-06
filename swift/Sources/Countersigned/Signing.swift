import Foundation
import CryptoKit

/// Anything that can countersign — the other half of `spec/PROTOCOL.md` §5.
///
/// The package deliberately does not choose a key store. A Secure Enclave key
/// cannot export its private half, so nothing here may ask for one: the
/// protocol needs exactly two things, a public key and a signature.
public protocol SigningKey: Sendable {
    /// base64 of the uncompressed SEC1 point — what the registry stores.
    var publicKeyBase64: String { get }
    /// False for keys a process can copy. Demos and tests must say so out loud.
    var isHardwareBacked: Bool { get }
    /// ECDSA P-256 / SHA-256, DER-encoded.
    func signature(for payload: Data) throws -> Data
}

/// A P-256 key in ordinary memory.
///
/// Not a secure element: whoever can read the process or the file can sign as
/// this device. For tests and demos — never to represent a person.
public struct SoftwareKey: SigningKey {
    private let key: P256.Signing.PrivateKey

    public init() { self.key = P256.Signing.PrivateKey() }

    public init(rawRepresentation: Data) throws {
        self.key = try P256.Signing.PrivateKey(rawRepresentation: rawRepresentation)
    }

    public var rawRepresentation: Data { key.rawRepresentation }
    public var publicKeyBase64: String { key.publicKey.x963Representation.base64EncodedString() }
    public var isHardwareBacked: Bool { false }

    public func signature(for payload: Data) throws -> Data {
        try key.signature(for: payload).derRepresentation
    }
}

public enum SigningError: Error, Equatable, CustomStringConvertible {
    /// A state is not a decision. Signing "open" would mean a device asserting
    /// something it cannot assert.
    case statusNotSignable(String)

    public var description: String {
        switch self {
        case .statusNotSignable(let status):
            return "status is not signable: \(status) (expected approved or rejected)"
        }
    }
}

public enum Signer {
    public static let signable = ["approved", "rejected"]

    /// Countersign one action and return the finished approval.
    ///
    /// `workspace` and `actionId` are bound into the signed bytes — that is what
    /// lets the verifier refuse an approval made for something else. The nonce is
    /// generated here unless given: it is what makes an approval single-use, so
    /// it must never be derived from the action's own content.
    public static func approve(_ action: Action,
                               key: some SigningKey,
                               workspace: String,
                               actionId: String,
                               deviceId: String,
                               status: String = "approved",
                               version: CanonicalVersion = .v3,
                               protocolName: String = "nino-go",
                               nonce: String? = nil,
                               at: String? = nil) throws -> Approval {
        guard signable.contains(status) else { throw SigningError.statusNotSignable(status) }

        let unsigned = Approval(
            workspace: workspace, actionId: actionId, status: status,
            digest: action.digest(version),
            nonce: nonce ?? Self.freshNonce(),
            at: at ?? ISO8601DateFormatter().string(from: Date()),
            deviceId: deviceId)
        let signature = try key.signature(for: unsigned.payload(version, protocolName: protocolName))
        return Approval(workspace: unsigned.workspace, actionId: unsigned.actionId,
                        status: unsigned.status, digest: unsigned.digest,
                        nonce: unsigned.nonce, at: unsigned.at, deviceId: unsigned.deviceId,
                        signature: signature.base64EncodedString())
    }

    static func freshNonce() -> String {
        var bytes = [UInt8](repeating: 0, count: 16)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return bytes.map { String(format: "%02x", $0) }.joined()
    }
}
