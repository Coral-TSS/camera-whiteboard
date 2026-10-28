# Third-party components

Camera Whiteboard original code is MIT licensed. Component licenses are separate; the complete app bundle is not "all MIT".

| Component | Version / revision | Role | License / source |
|---|---|---|---|
| VCamSample | `58b6d4b0e0c2c97fdffd66d23e7c8da6b89f570d` | Native Media Foundation source baseline | MIT; https://github.com/smourier/VCamSample |
| C++/WinRT | 3.0.260818.1 | Native build dependency | MIT; https://www.nuget.org/packages/Microsoft.Windows.CppWinRT |
| Windows Implementation Library | 1.0.260126.7 | Native build dependency | MIT; https://www.nuget.org/packages/Microsoft.Windows.ImplementationLibrary |
| Python | 3.13.17 build baseline | Bundled interpreter | PSF; see included license |
| PySide6 / Qt / Shiboken | 6.12.0 | Interface and image composition | Open-source Qt terms; see packaging/licenses/NOTICE.md |
| OpenCV headless | 5.0.0.93 package | Capture fallback and JPEG decoding | Apache 2.0 plus included third-party notices |
| NumPy | 2.5.4 | Image buffers | BSD and bundled component licenses |
| imageio-ffmpeg | 0.6.0 | Locates bundled FFmpeg executable | BSD-2-Clause wrapper |
| FFmpeg executable | Gyan 7.1 essentials build | DirectShow MJPEG subprocess | GPL-3.0-or-later; distinct from the wrapper's BSD license |
| PyInstaller | 6.22.3 | App packaging / bootloader | GPL with distribution exception |

See [distribution notices](../packaging/licenses/NOTICE.md) for bundled license texts, exact FFmpeg configuration and upstream source locations. Preserve notices and satisfy each component's source/distribution terms when publishing binaries.

## Vendored native changes

The upstream source is retained under `third_party/vcamsample/` with its LICENSE and COMMIT.txt. Local changes include diagnostic frame markers, a file-backed shared-frame reader, retry behavior, 1280×720 media types and a product CLSID. The implementation is not an unmodified upstream build.

Product identity: `{2B28F238-082E-4FE4-8142-3141306593D0}`. Do not register or remove upstream sample camera identities when installing/uninstalling this product.

NuGet packages and compiler outputs are restored/built locally and excluded from the clean source snapshot. No source code from OBS, BestCam or pyvirtualcam is intentionally vendored into this project.
