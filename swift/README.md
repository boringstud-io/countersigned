# Countersigned (Swift)

The signing half. An agent may prepare anything; nothing leaves without a signature made by a
key that lives on a person's device.

```swift
let action = Action(type: "mail", to: "studio@example.com",
                    subject: "Offer", body: "Hi,\nthe offer is attached.\n")

let verdict = try Verifier.verify(action: action, approval: approval, registry: registry,
                                  workspace: "acme/ops", actionId: "act-1")
```

`workspace` and `actionId` are what the *caller* is verifying for — not what the approval
claims. Passing them is not ceremony: a signature proves that someone signed that payload, not
that the payload belongs here.

Implements the [countersigned protocol](https://github.com/boringstud-io/countersigned/blob/main/spec/PROTOCOL.md):
canonical form (v3 and v4), SHA-256 digest, ECDSA P-256 signature, verification in the
prescribed order, and the contradiction pass.

## Install

```swift
.package(url: "https://github.com/boringstud-io/countersigned", from: "0.1.0")
```

The package depends only on Foundation and CryptoKit. On Apple hardware the private key
belongs in the Secure Enclave; this package does not choose the key store for you — it takes a
public key and verifies against it.

## Tests

`swift test` reads `vectors/vectors.json` at the repository root — the same file the Python
tests read. Both implementations must pass every vector.

## License

Apache 2.0.
