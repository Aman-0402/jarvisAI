# jarvis.spec — PyInstaller build spec for Jarvis.
# Build with: pyinstaller jarvis.spec --clean
# Output: dist/Jarvis/Jarvis.exe
#
# NOTE: the hidden_imports/collect_all list below is a best-effort
# starting point (see docs/superpowers/specs/2026-09-22-standalone-exe-design.md
# "Known risk" section) — a later task iterates on this based on actual
# build failures. Don't treat this file as final on first read.

from PyInstaller.utils.hooks import collect_all
from PyInstaller.building.build_main import Splash

datas = [
    ('jarvis/static', 'jarvis/static'),
    ('jarvis/assets', 'jarvis/assets'),
    ('config.yaml.example', '.'),
]
binaries = []
hidden_imports = []

# Libraries with dynamically-loaded backends that PyInstaller's static
# analysis tends to miss — collect_all pulls in their submodules, data
# files, and binaries.
for pkg in ['torch', 'ctranslate2', 'chromadb', 'openwakeword', 'pyaudio', 'pythonnet', 'language_tags', 'espeakng_loader', 'en_core_web_sm']:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hidden_imports += pkg_hiddenimports
    except Exception as e:
        print(f"[jarvis.spec] collect_all({pkg!r}) failed: {e}")

a = Analysis(
    ['pyinstaller_entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Native PyInstaller splash — shows immediately on double-click (before the
# bundled interpreter even finishes starting), closes via pyi_splash.close()
# once jarvis/wake.py's listener is actually live. See
# docs/superpowers/specs/2026-09-23-splash-screen-design.md.
splash = Splash(
    'jarvis/assets/splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(10, 390),
    text_size=12,
    text_color='white',
    text_default='Starting Jarvis...',
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    [],
    exclude_binaries=True,
    name='Jarvis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='jarvis/assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=False,
    name='Jarvis',
)
