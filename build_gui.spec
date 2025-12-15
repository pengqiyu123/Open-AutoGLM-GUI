# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('使用必读.txt', '.'),
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'phone_agent',
        'phone_agent.agent',
        'phone_agent.model',
        'phone_agent.model.client',
        'phone_agent.adb',
        'phone_agent.actions',
        'phone_agent.config',
        'gui',
        'gui.main_window',
        'gui.utils',
        'gui.utils.agent_runner',
        'gui.utils.system_checker',
        'gui.widgets',
        'gui.widgets.log_viewer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tensorflow',
        'torch',
        'matplotlib',
        'numpy.distutils',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
        'PIL._tkinter_finder',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    collect_submodules=False,  # 不收集所有子模块，加快速度
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用 UPX 压缩以加快打包速度
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 显示控制台窗口以查看进度
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

