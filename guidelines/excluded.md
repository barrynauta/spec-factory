# Rule sets considered and excluded

Rule sets that were considered for the engine rules and left out on purpose, with the reasons, so the question does not have to be argued again. A set can come back when its reasons no longer hold.

## Gang of Four design patterns (excluded 18 Nov 2026)

The 23 object-oriented design patterns of Gamma, Helm, Johnson and Vlissides, *Design Patterns* (1994), are not engine rules.

Reasons:

1. **The factory judges boundaries, not internals.** A build is accepted on its specifications, decisions and the black-box suite: what it does at its API and UI. How a component is structured inside is not something the specifications fix or the suite can see. GoF patterns are about that inside.
2. **The code is disposable** (see the principle in the [README](../README.md#principle-the-code-is-disposable)). When a component is regenerated from its specifications, its internal structure is not maintained by people, so patterns for maintainability inside the code buy little. To replace a store or a library, change the decision and regenerate.
3. **GoF is partly dated.** Several patterns are now built into languages and frameworks (Iterator, Observer, Factory through dependency injection), and Singleton is mostly seen as an anti-pattern. As rules they would mainly invite the code writer to add patterns for their own sake.
4. **Patterns without their problem make code worse.** A rule set of patterns rewards using them; the useful rule is the reverse. That is kept: [REUSE-06](./rules.md#reuse) asks for a named pattern where a recurring problem appears, and its note makes a pattern without that problem a finding. Step 70c reviews both.

For the same reasons, internal structure rules such as ports and adapters for every external dependency were not added either. What matters of them at the boundary is covered elsewhere: no implementation details in the contract (SOA-01), behaviour when a dependency is down (MSV-06, SOA-05), and the choice of products (REUSE-03, REUSE-05).

What would bring them back: components whose code is maintained by hand over years instead of regenerated, for example a build handed over to a maintenance team that patches it.
