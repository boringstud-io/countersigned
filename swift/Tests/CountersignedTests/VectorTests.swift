import Foundation
import Testing
@testable import Countersigned

/// The vectors are the contract between the implementations.
///
/// This suite reads `vectors/vectors.json` at the repository root — the same file
/// the Python tests read. If the two implementations disagree, one of them is
/// wrong, and without this file nobody would notice until a real approval is
/// rejected or a forged one accepted.
struct VectorTests {

    struct Vector: Decodable {
        let name: String
        let version: Int
        let note: String?
        let action: ActionFields?
        let canonical: String?
        let digest: String?
        let payload: String
        let signature: String
        let pubkey: String
        let expect: String
        let reason: String?
        let contentWithheld: Bool?
        let verifyFor: Binding?

        struct ActionFields: Decodable {
            let type: String
            let to: String?
            let cc: [String]?
            let subject: String?
            let attachments: [String]?
            let body: String

            var action: Action {
                Action(type: type, to: to, cc: cc ?? [], subject: subject,
                       attachments: attachments ?? [], body: body)
            }
        }

        struct Binding: Decodable {
            let workspace: String
            let actionId: String

            enum CodingKeys: String, CodingKey {
                case workspace
                case actionId = "action_id"
            }
        }

        enum CodingKeys: String, CodingKey {
            case name, version, note, action, canonical, digest, payload, signature
            case pubkey, expect, reason
            case contentWithheld = "content_withheld"
            case verifyFor = "verify_for"
        }

        var canonicalVersion: CanonicalVersion { CanonicalVersion(rawValue: version)! }
    }

    struct File: Decodable {
        let protocolName: String
        let vectors: [Vector]

        enum CodingKeys: String, CodingKey {
            case protocolName = "protocol"
            case vectors
        }
    }

    static let file: File = {
        // …/swift/Tests/CountersignedTests/VectorTests.swift → repository root
        let root = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // CountersignedTests
            .deletingLastPathComponent()   // Tests
            .deletingLastPathComponent()   // swift
            .deletingLastPathComponent()   // repository root
        let url = root.appendingPathComponent("vectors/vectors.json")
        let data = try! Data(contentsOf: url)
        return try! JSONDecoder().decode(File.self, from: data)
    }()

    static var vectors: [Vector] { file.vectors }

    /// Every vector's signature is genuine — including the tampered ones.
    ///
    /// This is the subtle part: tampering with the *action* does not break the
    /// signature, because the signature was made over the payload and the payload
    /// did not change. What breaks is the link between the payload's digest and
    /// the content. Keeping the two apart is why there are two tests.
    @Test(arguments: VectorTests.vectors.map(\.name))
    func signatureVerifiesAgainstItsOwnPayload(name: String) throws {
        let vector = try #require(Self.vectors.first { $0.name == name })
        #expect(Verifier.verifyPayload(Data(vector.payload.utf8),
                                       signature: vector.signature,
                                       pubkey: vector.pubkey),
                "\(vector.name): \(vector.note ?? "")")
    }

    /// Rebuild the canonical form from the action and compare byte for byte.
    @Test(arguments: VectorTests.vectors.filter { $0.action != nil }.map(\.name))
    func canonicalFormAndDigestMatch(name: String) throws {
        let vector = try #require(Self.vectors.first { $0.name == name })
        let action = try #require(vector.action).action
        #expect(action.canonical(vector.canonicalVersion) == vector.canonical)
        #expect(action.digest(vector.canonicalVersion) == vector.digest)
        #expect(Action.digest(of: try #require(vector.canonical)) == vector.digest)
    }

    /// A changed action no longer matches the signed payload.
    @Test(arguments: VectorTests.vectors
        .filter { $0.expect == "invalid" && $0.verifyFor == nil }.map(\.name))
    func tamperingBreaksTheLink(name: String) throws {
        let vector = try #require(Self.vectors.first { $0.name == name })
        let action = try #require(vector.action).action
        let signedDigest = vector.payload.split(separator: "|", omittingEmptySubsequences: false)[4]
        #expect(action.digest(vector.canonicalVersion) != String(signedDigest),
                "\(vector.name): \(vector.reason ?? "")")
    }

    /// A genuine signature for another workspace or action must be refused.
    /// An implementation that only checks the signature passes by accident.
    @Test(arguments: VectorTests.vectors.filter { $0.verifyFor != nil }.map(\.name))
    func bindingIsCheckedNotJustTheSignature(name: String) throws {
        let vector = try #require(Self.vectors.first { $0.name == name })
        let fields = vector.payload.split(separator: "|", omittingEmptySubsequences: false)
            .map(String.init)
        let approval = Approval(workspace: fields[1], actionId: fields[2], status: fields[3],
                                digest: fields[4], nonce: fields[5], at: fields[6],
                                deviceId: fields[7], signature: vector.signature)
        let registry = Registry(
            devices: [Device(deviceId: fields[7], pubkey: vector.pubkey, role: "owner")],
            roles: ["owner": ["mail", "publish"]])
        let binding = try #require(vector.verifyFor)
        #expect(throws: (any Error).self) {
            try Verifier.verify(action: try #require(vector.action).action,
                                approval: approval, registry: registry,
                                workspace: binding.workspace, actionId: binding.actionId)
        }
    }

    /// One vector must come from the deployed system — otherwise the suite only
    /// proves that we agree with ourselves.
    @Test func productionVectorIsPresent() {
        #expect(Self.vectors.contains { $0.contentWithheld == true })
    }

    /// The empty cc line is still a line. Confusing v3 and v4 would let a
    /// signature that does not cover cc pass as one that does.
    @Test func v4WithoutCCIsNotV3() {
        let action = Action(type: "mail", to: "a@example.com", subject: "Offer", body: "Hi")
        #expect(action.digest(.v3) != action.digest(.v4))
        #expect(action.canonical(.v4).contains("\ncc=\n"))
        #expect(!action.canonical(.v3).contains("cc="))
    }
}
