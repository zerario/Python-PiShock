# Changelog

## v1.2.0 (2025-05-30)

- Declare support for Python 3.13 and 3.14 (no code changes required)
- Drop support for Python 3.8
- Upgrade all locked dependencies

## v1.1.0 (2024-08-17)

- New random mode features:
    - Add `--init-delay`, waiting a random delay before the first operation.
    - `--pause` and `--spam-pause` now understand `h` / `m` / `s` suffixes like
      `--max-duration` already did.
    - `--max-duration` now also understands a `min-max` range to pick a random
      max duration.
- Add missing export of `pishock.httpapi.PiShockAPI` as `pishock.PiShockAPI`

## v1.0.3 (2024-01-12)

- Calling `.info()` on a `SerialShocker` now includes its shocker ID in the returned `name`.
- Just like `HTTPShocker`, `SerialShocker` now implements `__str__`, returning a string like `Serial shocker 1234 (/dev/ttyUSB0)`
- Random mode improvements:
    * Thanks to the changes above, using `pishock --serial random` now also results in nicer output.
    * `pishock random` now waits patiently until the shock/vibration is finished before sleeping for its pause period.
    * Fixed off-by-one, causing e.g. there still being an 1% chance of entering spam mode when it was, in fact, disabled.
    * When setting a `--spam-possibility` together with `--no-shock`, an error message is now shown, instead of causing an `AssertionError` later on.

## v1.0.2 (2024-01-12)

- Packaging / documentation improvements only, no code changes.

## v1.0.1 (2024-01-12)

- Packaging / documentation improvements only, no code changes.

## v1.0.0 (2024-01-12)

- Initial release
