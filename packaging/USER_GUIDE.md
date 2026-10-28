# Camera Whiteboard — User Guide

Requires Windows 11 x64 and camera access for desktop apps. Python, Qt, OpenCV and FFmpeg are all
bundled in this folder; you do not need OBS or any development tools.

1. Extract the whole `app` folder to a local disk.
2. Double-click `Install.cmd` once and approve the administrator prompt. It only copies the media
   source DLL into Program Files, registers it, and sets permissions on the frame folder in
   ProgramData. Close any client that is currently using the virtual camera before installing or
   updating.
3. Double-click `CameraWhiteboard.exe` and run it as a normal user. In your meeting app pick
   **Camera Whiteboard** (Windows may append a "Windows Virtual Camera" suffix).
4. The board menu item **Board position (remote view)** decides where the board appears in the
   outgoing video; the output is 1280×720. The window itself stays a 4:3 sheet. The panel follows
   the selected anchor and keeps it when you resize.
5. Strokes are not mirrored by default. Some meeting clients mirror their self-view; turn that off
   in the client or confirm with the remote side. Do not "fix" a mirrored self-view by flipping the
   outgoing video. **Mirror strokes** is only for when you deliberately want mirrored output.
6. Closing the board window only hides the board; video keeps streaming. Use the tray menu to quit.
   `Ctrl+Alt+F8` toggles mouse click-through, `Ctrl+Alt+F9` undoes the last stroke.
7. Uninstall: quit the app from the tray, close camera clients, then double-click `Uninstall.cmd`.
   It removes only this product's registration and runtime files, never other virtual cameras.

Keep the whole `app` folder, especially `_internal`. You can move the folder after installing,
because the registered DLL has been copied to a protected location. One installation serves one
interactive user on this PC; to use another Windows account, run the installer again from that
account. The installer does not enable the system camera privacy permission for you.

The build is unsigned, so Windows may show a SmartScreen prompt. This build passed automated tests
but has not been accepted on a clean machine or against a remote meeting peer. If a client always
crops or mirrors the video, check the client settings first. Logs and the current frame live in
`%ProgramData%\CameraWhiteboard`, are never uploaded, and are removed on uninstall.

Automatic recovery after a camera disconnect is limited: if the camera drops, quit and restart the
app. If the camera cannot deliver 720p MJPEG the capture falls back to a lower resolution. No need
to reinstall for that.

## Mirror the board without flipping your camera

In the board menu or tray menu, enable **Mirror board position + strokes**. It reflects the board's position and drawing horizontally while leaving the physical-camera picture unchanged. For example, a Top left placement is sent at the reflected Top right position. Turn it off to return to standard placement. The switch is off at startup.

Leave **Mirror strokes only** off when using the combined board switch, unless you intentionally want two stroke flips to cancel. The combined switch changes the outgoing board; it is not a preview-only setting. Verify the desired result with a remote participant when the meeting app also mirrors its self-view.
