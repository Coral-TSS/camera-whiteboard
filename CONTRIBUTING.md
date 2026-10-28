# Contributing

Camera Whiteboard is a Windows 11 desktop application that combines live webcam video with mouse-drawn diagrams. Small, reproducible fixes are welcome.

## Before changing code

1. Read README.md and docs/ARCHITECTURE.md.
2. Identify whether the change affects the UI, capture, composition, frame transfer, native source or packaging.
3. Reproduce the issue. Add a behavior test that fails for the intended reason before implementing a fix.
4. Keep the UI, device defaults, app-authored diagnostics and public documentation in English.

Use the build/test/package commands in README.md. Run the complete tests/ui discovery suite after relevant changes. Native changes require rebuilding the DLL; distribution changes require rerunning the bundled executable's dependency check.

## Reporting results

State what you tested and what remains untested. Record OS build, camera model and meeting-client version for hardware or client issues. Avoid attaching unredacted camera frames or local logs.

For AI-assisted changes, inspect current code and tests before relying on historical specifications. Keep changes focused, explain the behavioral effect, and do not claim physical-camera or meeting validation from mocks or in-process DLL tests.

## Contribution areas

- Recover from camera unplug/reconnect without retaining stale images.
- Guarantee a consistent shared-frame snapshot through pixel copying.
- Test install/update/uninstall on a clean Windows 11 machine.
- Add remote-client acceptance records.
- Improve usability without introducing an OBS dependency or requiring a separately installed runtime.
