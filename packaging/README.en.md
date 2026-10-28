# Camera Whiteboard — English release

Draw your explanation. Stay on camera.

- **app/** contains the Windows 11 x64 application and bundled runtimes. Run **Install.cmd** once, then launch **CameraWhiteboard.exe** as your normal Windows user. Read [the user guide](app/USER_GUIDE.md).
- **source/** contains the clean source snapshot. Start with [the project README](source/README.md).
- **SHA256SUMS.txt** lists file hashes.

The interface, device name, app-authored errors and shipped user guide are English. No OBS, separate Python installation or development tools are required on the destination PC.

Publish source/ as your GitHub repository and the application ZIP as a GitHub Releases asset. Third-party libraries retain their own licenses; see app/licenses/.

Automated and bundled-dependency checks do not replace clean-PC installation or remote meeting acceptance; see source/validation/english-release-2026-10-27.md.
