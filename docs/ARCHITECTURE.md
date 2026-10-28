# Architecture: follow a frame

## Current implementation

1. `camera.py` starts a bundled FFmpeg subprocess to request DirectShow MJPEG from the first/cached video device. A worker decodes the newest frame. OpenCV is the lower-resolution fallback.
2. `canvas.py` stores strokes and undo history without Qt. `viewport.py` exposes the drawing sheet and click-through behavior; `render.py` rasterizes strokes.
3. `compositor.py` combines a camera frame and a white 4:3 panel. `layout.py` computes the panel anchor in the outgoing 1280×720 frame. Content mirroring does not affect panel location.
4. `publisher.py` writes a 64-byte header and premultiplied BGRA pixels to a file mapping, on a roughly 33 ms UI timer. Repeated publication keeps the stream timestamp fresh even when strokes are unchanged.
5. `SharedFrameSource.cpp` in the native source reads the mapped file. The DLL exposes RGB32/NV12 through Media Foundation. Windows loads it through Camera Frame Server; meeting apps choose the resulting virtual camera.
6. `virtualcam.py` manages the Session/CurrentUser virtual-camera instance. Normal exit stops/removes it. `bootstrap.py` begins startup before importing the larger GUI dependencies.

## Identity and paths

Product CLSID: `{2B28F238-082E-4FE4-8142-3141306593D0}`. Default device label: **Camera Whiteboard**. A sample-CLSID fallback remains in the legacy development wrapper; the distribution includes a DLL supporting the product identity.

Development frames/logs use `.run/` when that directory exists. Packaged applications use `%ProgramData%\CameraWhiteboard`. First-time installation copies the media source to `%ProgramFiles%\CameraWhiteboard`, registers its COM class and grants frame access to the installing user and required system hosts. Actual service-host ACL acceptance remains a test task.

The app does not use the empty `native/` planning directories as an engine. Python owns capture and composition today; the C++ source lives under `third_party/vcamsample/VCamSampleSource`.

## Verification boundaries

The sequence counter is intended to identify in-progress writes, but the current native reader does not recheck it after pixel copying. It is not yet a complete consistent-snapshot protocol. Camera disconnect handling can retain a stale image; this is another open issue.

`--check-bundle <report.json>` loads the bundled GUI dependencies and FFmpeg, exercises composition and checks the product class factory without registering a camera or capturing video. It is useful for packaging regressions but does not test Frame Server activation or a remote meeting peer.

Interface strings are in `i18n.py`; English is the default and fallback. User configuration is in `config/app.json`. Historical specifications may differ from current behavior: verify against code and tests.

## Board-only reflection

`set_board_mirror()` reflects the panel rectangle with `x = output_width - x - width` and flips the stroke layer. Camera drawing is untouched. The stroke-only toggle remains independent; its flip combines with the board flip using XOR. Tests use an asymmetric camera base to verify camera pixels remain unchanged, including when the board is hidden.
