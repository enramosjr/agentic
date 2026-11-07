# Proposed local qualification storage setup

Status: Authorized and completed for local qualification on 2026-11-07. The
task-owned work volume, loop device and backing volume have been removed. This
setup is separate from the candidate executor, which creates no privileged
containers or loop devices.

Authorization from the user in this chat: "I approve the proposed privileged
loop-device setup in the dedicated Podman WSL2 backend for local qualification."

## Why it is needed

The real controller reached AGENTIC's lifecycle command inside a restricted
container, but lifecycle refused tmpfs-backed scratch. Removing that requirement
would weaken an existing contract. The executor now requires an independently
provisioned disk-backed work volume, with capacity bounded by the approved policy.

## Safer existing-volume option

Provide an empty Docker/Podman volume backed by a dedicated filesystem of at most
256 MiB, writable by UID/GID 65534. Set `AGENTIC_WORK_VOLUME` to its name. The
executor verifies disk backing, capacity and effective isolation before candidate
execution. An ordinary unbounded local volume is insufficient. The independent
provisioner must reset/discard it after each execution.

## Optional setup requiring explicit approval

For local qualification only, authorize the following bounded setup in the already
created Podman WSL2 backend, through connection `agentic-trusted-ci-root`:

1. Create task-owned backing volume `agentic-qualification-backing`.
2. Use the already downloaded official runtime image
   `docker.io/library/python@sha256:2784af835b90070d9d37d3aa5aa01a3e825d88436b0d58f7776d2cdcb6780f9e`
   for one trusted infrastructure helper. It runs with `--privileged`,
   `--network=none`, `--pull=never`, and only that backing volume mounted at `/disk`.
   No candidate source, controller checkout, credentials or result paths are mounted.
3. That helper creates a 256 MiB file, formats ext4 with root ownership 65534:65534,
   and attaches a newly allocated loop device. It executes only fixed infrastructure
   utilities, never candidate code.
4. Configure `agentic-qualification-work` as the engine-managed ext4 volume using
   that device with `rw,nosuid,nodev`; use it for the strict container/controller tests.
5. After the tests, remove the task-owned work volume, detach only the recorded
   task-owned loop device, and remove the backing volume. Reset the filesystem
   between test cases; never reuse candidate data as a new execution's input.

Privileged execution grants broad access to the Linux backend's kernel/devices.
The WSL2 backend can integrate with host filesystems, so this is a real host-boundary
expansion despite the fixed trusted image and narrow intended operations.
Automatic approval review initially rejected it because that expansion had not
been explicitly authorized. The user's subsequent approval above authorizes the
documented local setup; it does not grant production authority credentials.
Supplying an independently provisioned volume avoids this action.

This local setup cannot establish deployed enforcement. A separate administrator
must still provision the trusted authority, App credentials, restricted coding
identity, hosting rules and disposable hosted qualification target outside the
modifying agent's administrative environment.
