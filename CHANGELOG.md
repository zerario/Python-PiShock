# Changelog

## v1.0.3 (unreleased)

- Calling `.info()` on a `SerialShocker` now includes its shocker ID in the returned `name`.
- Just like `HTTPShocker`, `SerialShocker` now implements `__str__`, returning a string like `Serial shocker 1234 (/dev/ttyUSB0)`.
- Consequently, using `pishock --serial random` now also results in nicer output.

## v1.0.2 (2024-01-12)

- Packaging / documentation improvements only, no code changes.

## v1.0.1 (2024-01-12)

- Packaging / documentation improvements only, no code changes.

## v1.0.0 (2024-01-12)

- Initial release
