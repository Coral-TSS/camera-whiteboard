# Third-party notices

Camera Whiteboard original code and VCamSample are MIT licensed. This does not replace component licenses.

- Python 3.13.17: PSF license, included text; https://www.python.org/downloads/source/
- PySide6 / Qt / Shiboken 6.12.0: package metadata offers LGPL-3.0 / GPL alternatives; this bundle dynamically links Qt Core/Gui/Widgets under the open-source terms. Qt libraries can be replaced in _internal; reverse engineering for debugging modifications is permitted to the extent required by their license. Source: https://download.qt.io/official_releases/QtForPython/ and https://download.qt.io/official_releases/qt/ . Component license texts included below.
- OpenCV 5.0.0.93: included LICENSE and LICENSE-3RD-PARTY; https://github.com/opencv/opencv-python
- NumPy 2.5.4: included BSD and bundled component license texts; https://github.com/numpy/numpy
- imageio-ffmpeg 0.6.0: BSD-2-Clause wrapper; https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0
- Bundled ffmpeg-win-x86_64-v7.1.exe is a separate GPL-3.0-or-later executable from Gyan, NOT BSD/MIT. Exact version/configuration is recorded in FFmpeg-build.txt. Source release: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz ; build provider/library information: https://www.gyan.dev/ffmpeg/builds/ . Keep these notices with any redistribution and provide corresponding sources/build inputs as required by the component licenses.
- PyInstaller bootloader: GPL with distribution exception, included COPYING.

The installed Qt wheel ships a commercial-license notice as well; that notice does not remove the open-source license alternatives declared in its metadata. This bundle includes the open-source license texts separately. This notice is a component inventory, not a relicensing of third-party binaries.
