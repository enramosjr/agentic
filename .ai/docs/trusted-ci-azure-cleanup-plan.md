# Azure cleanup phase refinement

This read-only planner refinement resolves an implementation decision within
approved adopter-owned plan step 7 (R7, R10); it changes no product requirement.
Privileged setup, live qualification and activation remain held.

The old loop mixed ownership acquisition, deletion requests and eventual
inventory polling. Generic ARM rows can omit typed properties and remain visible
after resources have disappeared. An accepted DELETE request also does not prove
the provider operation completed. Repeating capture or deletion in that loop is
unsafe and produced deterministic local failures.

Use a monotonic trusted handle with a separate operation state per VM, NIC and
disk: no state → pending → confirmed, or no state → authenticated absent. An
ambiguous pending operation requires trusted recovery; never reset it by guessing.

1. Fresh typed VM readback validates job identity, current NIC/root-disk mappings,
   no extra disks, and the root disk's immutable UID and VM association. A UID
   observed earlier is a comparison baseline, not fresh deletion authorization.
2. Issue one scoped typed CLI deletion without `--no-wait`. Advance only after
   the CLI's provider-operation completion witness; timeout/failure stays pending.
3. Poll exact identities in generic inventory, without recapture or repeated
   DELETE. Bound the wait and fail closed on ambiguity or timeout.
4. For surviving NIC/disk resources, perform their own fresh typed preflight,
   enforce ownership/detachment, issue one completed DELETE and poll absence.
   A root disk needs the captured immutable UID; name or tags alone are insufficient.
5. A specifically authenticated ARM `ResourceNotFound` may enter absence polling.
   Generic CLI failures, authentication/network errors and unrelated 404s cannot.
6. Sweep all three inventories at the end. A reappearing identity blocks cleanup;
   it must not trigger deletion of a possible replacement.

Focused regressions exercise generic identity-only rows, cached-UID mapping
changes, stale VM and disk inventories, retained disks, foreign mappings and
attachments, unknown orphans and partial launch. Typed deletion and precise
not-found handling have separate transport tests. Local fixtures do not qualify
Azure API behavior, RBAC or hosted cleanup.

The CLI's blocking-delete behavior is documented by Microsoft for
[`az vm delete`](https://learn.microsoft.com/en-us/cli/azure/vm#az-vm-delete).
Token expiry uses the CLI's POSIX `expires_on` field; the
[Azure account CLI documentation](https://learn.microsoft.com/en-us/cli/azure/account#az-account-get-access-token)
defines that field. Tokens remain in process memory and HTTPS headers, never argv.
