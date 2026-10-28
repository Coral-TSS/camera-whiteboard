# English release verification — 2026-10-27

Scope: English application menus, device defaults, status/error text, startup logs, user guide and release documentation. Existing Chinese design/history notes and internal source comments are retained as history.

Four new behavior tests initially failed for non-English default/fallback configuration, a hard-coded Chinese tray submenu and Chinese virtual-camera errors. They pass after changes. The complete suite contains 110 tests.

README now includes a use-case overview, installation, controls, a pipeline diagram, exact build/test/export entry points, an AI contributor code map, current limitations and license boundaries. CONTRIBUTING.md, docs/ARCHITECTURE.md and llms.txt provide English development entry points. Source export includes these files.

A fresh English application/source bundle is built from this tree. Its bundled dependency check reports the actual language and camera name in addition to GUI, composition, FFmpeg and native factory results. This test does not register a device or capture camera video. Clean-machine installation and remote meeting acceptance remain unverified for this release.

## Final results

- Full automated suite: **110 tests passed**. A pre-existing QImage.mirrored deprecation warning remains.
- Packaged executable: Windows platform plugin and all bundled dependency checks passed with PATH limited to Windows directories. Reported language: en; device: Camera Whiteboard; placement menu: Board position (remote view).
- Application runtime string scan found no Chinese app-authored string literals. Historical comments/specifications are retained.
- Source README, contribution and architecture links resolved locally.
- No device registration, physical-camera capture, clean-PC install or remote meeting session was performed in this language-only verification.

## Board-only mirror update

User requested reflecting the board's position and drawing, explicitly excluding the camera. Added **Mirror board position + strokes** to both board and tray menus, default off. Four new tests exercise position reflection/restoration, asymmetric strokes, unchanged asymmetric camera pixels, hidden-board behavior and independent stroke-flip interaction. The actual menu action is exercised by the English menu test. Full suite: **114 tests passed**. No physical-camera or meeting-client test was performed for this update.
