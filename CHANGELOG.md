# Changelog

## v1.0.4 (unreleased)

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
