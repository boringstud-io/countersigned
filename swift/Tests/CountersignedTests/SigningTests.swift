import Testing
import Foundation
@testable import Countersigned

/// The signing half. Every test here is one sentence about the protocol.
@Suite("Signing")
struct SigningTests {
    static let workspace = "owner/repo"
    static let actionId = "go-2026-09-06-01"

    func registry(for key: some SigningKey, role: String = "owner",
                  mayApprove: [String] = ["email"]) -> Registry {
        Registry(devices: [Device(deviceId: "iphone", pubkey: key.publicKeyBase64,
                                  role: role, name: "Demo")],
                 roles: [role: mayApprove])
    }

    var action: Action {
        Action(type: "email", to: "studio@example.com", subject: "Offer",
               attachments: ["offer.pdf"], body: "Attached.")
    }

    @Test("what this package signs it also verifies", arguments: [CanonicalVersion.v3, .v4])
    func roundTrip(version: CanonicalVersion) throws {
        let key = SoftwareKey()
        let approval = try Signer.approve(action, key: key, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone",
                                          version: version)
        let verdict = try Verifier.verify(action: action, approval: approval,
                                          registry: registry(for: key),
                                          workspace: Self.workspace, actionId: Self.actionId)
        #expect(verdict.version == version)
        #expect(verdict.device.deviceId == "iphone")
    }

    @Test("a rejection is signed the same way as an approval")
    func rejection() throws {
        let key = SoftwareKey()
        let approval = try Signer.approve(action, key: key, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone",
                                          status: "rejected")
        #expect(approval.status == "rejected")
        _ = try Verifier.verify(action: action, approval: approval, registry: registry(for: key),
                                workspace: Self.workspace, actionId: Self.actionId)
    }

    @Test("only a decision can be signed")
    func openIsNotADecision() {
        #expect(throws: SigningError.statusNotSignable("open")) {
            try Signer.approve(action, key: SoftwareKey(), workspace: Self.workspace,
                               actionId: Self.actionId, deviceId: "iphone", status: "open")
        }
    }

    @Test("an approval does not travel to another action")
    func boundToAction() throws {
        let key = SoftwareKey()
        let approval = try Signer.approve(action, key: key, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone")
        #expect(throws: (any Error).self) {
            try Verifier.verify(action: action, approval: approval, registry: registry(for: key),
                                workspace: Self.workspace, actionId: "go-other")
        }
    }

    @Test("an approval does not travel to another workspace")
    func boundToWorkspace() throws {
        let key = SoftwareKey()
        let approval = try Signer.approve(action, key: key, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone")
        #expect(throws: (any Error).self) {
            try Verifier.verify(action: action, approval: approval, registry: registry(for: key),
                                workspace: "someone/else", actionId: Self.actionId)
        }
    }

    @Test("changing one character of the action breaks the approval")
    func tampering() throws {
        let key = SoftwareKey()
        let approval = try Signer.approve(action, key: key, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone")
        let tampered = Action(type: "email", to: "attacker@example.com", subject: "Offer",
                              attachments: ["offer.pdf"], body: "Attached.")
        #expect(throws: (any Error).self) {
            try Verifier.verify(action: tampered, approval: approval, registry: registry(for: key),
                                workspace: Self.workspace, actionId: Self.actionId)
        }
    }

    @Test("each approval gets its own nonce")
    func nonces() throws {
        let key = SoftwareKey()
        var seen = Set<String>()
        for _ in 0..<50 {
            seen.insert(try Signer.approve(action, key: key, workspace: Self.workspace,
                                           actionId: Self.actionId, deviceId: "iphone").nonce)
        }
        #expect(seen.count == 50)
    }

    @Test("a role that may not approve this type is refused")
    func role() throws {
        let key = SoftwareKey()
        let approval = try Signer.approve(action, key: key, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone")
        #expect(throws: (any Error).self) {
            try Verifier.verify(action: action, approval: approval,
                                registry: registry(for: key, role: "reader", mayApprove: ["note"]),
                                workspace: Self.workspace, actionId: Self.actionId)
        }
    }

    @Test("a software key survives a round trip through its raw bytes")
    func rawRoundTrip() throws {
        let key = SoftwareKey()
        let restored = try SoftwareKey(rawRepresentation: key.rawRepresentation)
        #expect(restored.publicKeyBase64 == key.publicKeyBase64)
        let approval = try Signer.approve(action, key: restored, workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone")
        _ = try Verifier.verify(action: action, approval: approval, registry: registry(for: key),
                                workspace: Self.workspace, actionId: Self.actionId)
    }

    @Test("a software key admits that it is one")
    func honesty() {
        // The demo leans on this: a laptop must not look like a Secure Enclave.
        #expect(SoftwareKey().isHardwareBacked == false)
    }

    @Test("the signature is DER, not raw r||s")
    func derEncoding() throws {
        // Raw r||s is 64 bytes; DER carries a SEQUENCE header. A signer that
        // emitted raw would fail only in production, against the real verifier.
        let approval = try Signer.approve(action, key: SoftwareKey(), workspace: Self.workspace,
                                          actionId: Self.actionId, deviceId: "iphone")
        let raw = try #require(Data(base64Encoded: approval.signature))
        #expect(raw.first == 0x30)
        #expect(raw.count != 64)
    }
}
