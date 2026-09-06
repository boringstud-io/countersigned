import Foundation
import CryptoKit

/// The canonical form — the exact bytes that get signed.
///
/// Specified in `spec/PROTOCOL.md` §3. Every rule here is load-bearing; the
/// whitespace rule below once cost a valid approval.
public enum CanonicalVersion: Int, Sendable, CaseIterable {
    case v3 = 3
    case v4 = 4
}

/// One action with an outside effect: a mail, a publication, a contract.
public struct Action: Equatable, Sendable {
    public let type: String
    public let to: String?
    public let cc: [String]
    public let subject: String?
    public let attachments: [String]
    public let body: String

    public init(type: String, to: String? = nil, cc: [String] = [],
                subject: String? = nil, attachments: [String] = [], body: String) {
        self.type = type
        self.to = to
        self.cc = cc
        self.subject = subject
        self.attachments = attachments
        self.body = body
    }

    /// Field keys are part of the signed bytes and therefore fixed forever.
    /// They are German because that is what the deployed system signs — renaming
    /// them would change every digest and invalidate existing approvals.
    private enum Key {
        static let type = "typ", to = "an", cc = "cc"
        static let subject = "betreff", attachments = "anhang", body = "text"
    }

    /// Collapse every run of whitespace to a single space, then trim.
    ///
    /// Exactly `" ".join(value.split())` on the other side. Not cosmetic: the two
    /// implementations once disagreed here — one replaced newlines only, the other
    /// folded all whitespace — and a subject with two spaces produced two different
    /// digests. A genuine approval would have been rejected as invalid.
    public static func oneLine(_ value: String?) -> String {
        (value ?? "").split(whereSeparator: \.isWhitespace).joined(separator: " ")
    }

    private static func join(_ entries: [String]) -> String {
        entries.map(oneLine).joined(separator: ",")
    }

    public func canonical(_ version: CanonicalVersion = .v3) -> String {
        var lines = ["\(Key.type)=" + Self.oneLine(type),
                     "\(Key.to)=" + Self.oneLine(to)]
        if version == .v4 {
            lines.append("\(Key.cc)=" + Self.join(cc))
        }
        lines += ["\(Key.subject)=" + Self.oneLine(subject),
                  "\(Key.attachments)=" + Self.join(attachments),
                  // Last on purpose: the body may contain anything, newlines included.
                  "\(Key.body)=" + body]
        return lines.joined(separator: "\n")
    }

    public func digest(_ version: CanonicalVersion = .v3) -> String {
        Self.digest(of: canonical(version))
    }

    /// SHA-256 over the UTF-8 bytes, lowercase hex.
    public static func digest(of canonical: String) -> String {
        SHA256.hash(data: Data(canonical.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }
}
