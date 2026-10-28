"""Export a clean source tree and a self-contained Windows distribution."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

SOURCE_DIRS = ('ui', 'native', 'tests', 'scripts', 'packaging', 'config', 'docs', 'specs',
               'validation', 'third_party')
SOURCE_FILES = ('README.md', 'CONTRIBUTING.md', 'llms.txt', 'LICENSE', 'CMakeLists.txt', 'requirements.txt',
                'requirements-dev.txt', 'requirements-lock.txt', '.gitignore',
                '.gitattributes', '.editorconfig', '.clang-format')
EXCLUDED = {'.git', '.venv', '.run', '.build', '.vs', '.idea', '.workbuddy',
            '__pycache__', '.pytest_cache', 'packages', 'x64', 'debug', 'release',
            'build', 'dist', 'tools', 'ipch'}
EXTENSIONS = {'.py', '.cpp', '.h', '.hpp', '.c', '.md', '.txt', '.json', '.ps1',
              '.cmd', '.bat', '.spec', '.vcxproj', '.filters', '.sln', '.props',
              '.targets', '.config', '.rc', '.def', '.ico', '.manifest', '.gitkeep'}


LANG_DEFAULTS = {'en': {'deviceName': 'Camera Whiteboard'}}


def export_release(root: Path, output: Path, language: str = 'en') -> None:
    root, output = root.resolve(), output.resolve()
    built = root / 'packaging/dist/CameraWhiteboard'
    dll = root / 'third_party/vcamsample/x64/Release/VCamSampleSource.dll'
    required = [built / 'CameraWhiteboard.exe', dll, root / 'LICENSE',
                root / 'third_party/vcamsample/LICENSE', root / 'packaging/install.ps1',
                root / 'packaging/uninstall.ps1', root / 'packaging/USER_GUIDE.md']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f'Build/release input missing: {path}')
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite existing bundle: {output}')
    if root == output or root.is_relative_to(output):
        raise ValueError('Output cannot contain the project root')
    output.mkdir(parents=True)
    source = output / 'source'
    source.mkdir()
    for name in SOURCE_FILES:
        path = root / name
        if path.is_file():
            shutil.copy2(path, source / name)
    for directory in SOURCE_DIRS:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob('*'):
            relative = path.relative_to(root)
            if any(part.lower() in EXCLUDED or part.lower().startswith('dist')
                   for part in relative.parts[:-1]):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() not in EXTENSIONS and path.name not in ('LICENSE', 'CMakeLists.txt'):
                continue
            dest = source / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    app = output / 'app'
    shutil.copytree(built, app)
    (app / 'native').mkdir(exist_ok=True)
    shutil.copy2(dll, app / 'native/CameraWhiteboardSource.dll')
    for name in ('install.ps1', 'uninstall.ps1'):
        shutil.copy2(root / 'packaging' / name, app / name)
    guide = root / 'packaging' / f'USER_GUIDE.{language}.md'
    if not guide.is_file():
        guide = root / 'packaging' / 'USER_GUIDE.md'
    shutil.copy2(guide, app / 'USER_GUIDE.md')
    for name in ('Install.cmd', 'Uninstall.cmd'):
        script = name.split('.')[0].lower() + '.ps1'
        (app / name).write_bytes(
            ('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File '
             f'"%~dp0{script}"\r\nif errorlevel 1 (echo Failed. See message above.)\r\npause\r\n').encode('ascii'))
    shutil.copytree(root / 'config', app / 'config', dirs_exist_ok=True)
    app_config = app / 'config' / 'app.json'
    data = json.loads(app_config.read_text(encoding='utf-8')) if app_config.is_file() else {}
    data['language'] = language
    data['deviceName'] = LANG_DEFAULTS.get(language, {}).get('deviceName', data.get('deviceName', ''))
    app_config.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (app / 'licenses').mkdir(exist_ok=True)
    shutil.copy2(root / 'LICENSE', app / 'licenses/CameraWhiteboard-MIT.txt')
    shutil.copy2(root / 'third_party/vcamsample/LICENSE', app / 'licenses/VCamSample-MIT.txt')
    notices = root / 'packaging/licenses'
    if notices.exists():
        shutil.copytree(notices, app / 'licenses', dirs_exist_ok=True)
    readme = root / 'packaging' / f'README.{language}.md'
    if readme.is_file():
        shutil.copy2(readme, output / 'README.md')
    else:
        (output / 'README.md').write_text(
            '# Camera Whiteboard\n\n'
            '- `source/`: clean source snapshot for GitHub.\n'
            '- `app/`: Windows 11 x64 distribution. Run Install.cmd once, then '
            'CameraWhiteboard.exe. See app/USER_GUIDE.md.\n\n'
            'Publish source code in Git and application ZIPs as GitHub Releases assets.\n',
            encoding='utf-8')
    hashes = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            hashes.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}')
    (output / 'SHA256SUMS.txt').write_text('\n'.join(hashes) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', default='en', choices=('en',),
                        help='Distribution language (English); saved in app/config/app.json')
    args = parser.parse_args()
    export_release(args.root, args.output, args.language)
    print(f'Exported: {args.output.resolve()}')
