---
name: swift-swiftui-principal-engineer
description: Swift and SwiftUI pitfalls, validation commands, and review checklist; load for Swift/SwiftUI work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# Swift / SwiftUI Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read `Package.swift` or the Xcode project/workspace settings (deployment targets, Swift language mode, strict-concurrency level), lint config, and CI before choosing APIs. Use only APIs available at the deployment target; follow the existing architecture (MVVM/TCA/etc.) and persistence choice.

## Pitfalls to check

- **Concurrency:** UI/model state mutated off `@MainActor`; `Sendable` violations papered over with `@unchecked Sendable` or `nonisolated(unsafe)`; unstructured `Task {}` with no ownership or cancellation; ignoring `Task.isCancelled`/`CancellationError`; blocking calls in async contexts; actor reentrancy assumptions.
- **Memory:** retain cycles in closures (`[weak self]` / `[unowned self]` chosen deliberately); strong delegate references; observers and Combine subscriptions not stored/cancelled.
- **SwiftUI state:** wrong property wrapper (`@State` vs. `@StateObject` vs. `@Bindable`/`@Observable` vs. `@ObservedObject`) causing reset or duplicate model creation; work in `body`; state placed too high; `onAppear` side effects firing repeatedly; unstable identity in `ForEach`.
- **Optionals and errors:** force unwraps/`try!`/`fatalError` on runtime-dependent paths; silent `try?`; stringly-typed errors; error states not surfaced in UI.
- **Value vs. reference:** reference types where value types fit; shared mutable class state without isolation.
- **Platform:** APIs unavailable at the deployment target without `#available`; missing entitlements/Info.plist usage strings; platform conditionals leaking into shared code.
- **Accessibility/UI:** missing accessibility labels, Dynamic Type, and Dark Mode support; hard-coded strings where localization exists.
- **Persistence/network:** SwiftData/Core Data threading and migration; `URLSession` without timeouts, cancellation, or status validation; `Codable` shape changes breaking stored data.
- **Security:** secrets in source or `UserDefaults`; sensitive data in logs (use Keychain for credentials).

## Tests

- Unit-test logic with Swift Testing or XCTest per the repo; test view models/state rather than view internals; UI tests for critical flows. Inject clocks, network, and storage via protocols or closures.
- A bug fix gets a regression test that fails before the fix.

## Validation commands

Use the repo's own. Typical: `swift build`, `swift test`, `xcodebuild test -scheme <Scheme> -destination '<destination>'`, `swiftlint`, `swift-format lint`.

## Review checklist

- Isolation correct: UI on `@MainActor`, no unchecked `Sendable` escape hatches.
- Tasks owned and cancellable; no retain cycles.
- Property wrappers match ownership; no work in `body`.
- Availability, accessibility, and localization handled.
- Builds and tests pass; diff contains no unrelated edits.
