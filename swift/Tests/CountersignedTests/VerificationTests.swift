import Foundation
import CryptoKit
import Testing
@testable import Countersigned

/// Verification order and refusals — `spec/PROTOCOL.md` §6.
struct VerificationTests {

    static let key = P256.Signing.PrivateKey()
    static var pubkey: String { key.publicKey.x963Representation.base64EncodedString() }

    static let action = Action(type: "mail", to: "a@example.com", subject: "Offer", body: "Hi")

    static func signed(_ action: Action = action, status: String = "approved",
                       nonce: String = "n-1", version: CanonicalVersion = .v3,
                       workspace: String = "acme/ops", actionId: String = "act-1",
                       deviceId: String = "dev-1") throws -> Approval {
        let unsigned = Approval(workspace: workspace, actionId: actionId, status: status,
                                digest: action.digest(version), nonce: nonce,
                                at: "2026-09-06T10:00:00Z", deviceId: deviceId)
        let signature = try key.signature(for: try unsigned.payload(version))
        return Approval(workspace: workspace, actionId: actionId, status: status,
                        digest: unsigned.digest, nonce: nonce, at: unsigned.at,
                        deviceId: deviceId,
                        signature: signature.derRepresentation.base64EncodedString())
    }

    static func registry(role: String = "owner", usedNonces: Set<String> = [],
                         knownKeys: [String: String] = [:]) -> Registry {
        Registry(devices: [Device(deviceId: "dev-1", pubkey: pubkey, role: role)],
                 roles: ["owner": ["mail", "publish"], "editor": []],
                 usedNonces: usedNonces, knownKeys: knownKeys)
    }

    static func check(_ approval: Approval, action: Action = action,
                      registry: Registry? = nil,
                      workspace: String = "acme/ops", actionId: String = "act-1") throws -> Verdict {
        try Verifier.verify(action: action, approval: approval,
                            registry: registry ?? Self.registry(),
                            workspace: workspace, actionId: actionId)
    }

    @Test func validApprovalPasses() throws {
        let verdict = try Self.check(Self.signed())
        #expect(verdict.version == .v3)
        #expect(verdict.device.deviceId == "dev-1")
    }

    @Test func changedBodyIsRefused() throws {
        let approval = try Self.signed()
        let changed = Action(type: "mail", to: "a@example.com", subject: "Offer",
                             body: "Hi — and ship it")
        #expect(throws: VerificationError.signatureDoesNotVerify) {
            try Self.check(approval, action: changed)
        }
    }

    @Test func unknownDeviceIsRefused() throws {
        #expect(throws: VerificationError.unknownDevice("dev-9")) {
            try Self.check(Self.signed(deviceId: "dev-9"))
        }
    }

    /// Device replaced or restored — invalid until a human confirms.
    @Test func changedPublicKeyIsRefused() throws {
        let approval = try Self.signed()
        #expect(throws: VerificationError.deviceKeyChanged("dev-1")) {
            try Self.check(approval, registry: Self.registry(knownKeys: ["dev-1": "AAAA"]))
        }
    }

    @Test func roleWithoutRightIsRefused() throws {
        let approval = try Self.signed()
        #expect(throws: VerificationError.roleMayNotApprove(role: "editor", type: "mail")) {
            try Self.check(approval, registry: Self.registry(role: "editor"))
        }
    }

    @Test func replayIsRefused() throws {
        let approval = try Self.signed()
        #expect(throws: VerificationError.replay(nonce: "n-1")) {
            try Self.check(approval, registry: Self.registry(usedNonces: ["n-1"]))
        }
    }

    @Test func statusMustBeSignable() throws {
        #expect(throws: VerificationError.statusNotSignable("open")) {
            try Self.check(Self.signed(status: "open"))
        }
    }

    /// The whole point of binding the workspace into the payload. The signature
    /// below is genuine — it just belongs to another data space.
    @Test func approvalForAnotherWorkspaceDoesNotTransfer() throws {
        let approval = try Self.signed(workspace: "other/repo")
        #expect(throws: VerificationError.wrongWorkspace(claimed: "other/repo",
                                                         expected: "acme/ops")) {
            try Self.check(approval)
        }
    }

    @Test func approvalMovedToAnotherActionDoesNotTransfer() throws {
        let approval = try Self.signed()
        #expect(throws: VerificationError.wrongAction(claimed: "act-1", expected: "act-2")) {
            try Self.check(approval, actionId: "act-2")
        }
    }

    /// A payload that can be re-split in more than one way can be forged.
    @Test func separatorInAFieldIsRefusedWhenBuildingThePayload() {
        let approval = Approval(workspace: "acme/ops|evil", actionId: "act-1",
                                status: "approved", digest: "d", nonce: "n",
                                at: "2026-09-06T10:00:00Z", deviceId: "dev-1")
        #expect(throws: Approval.PayloadError.fieldContainsSeparator("acme/ops|evil")) {
            try approval.payload()
        }
    }
}
