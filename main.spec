# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
import os

datas = []
datas += collect_data_files('gradio_client')
datas += collect_data_files('gradio')
datas += collect_data_files('gradio_calendar')
datas += collect_data_files('gradio_log')

datas += collect_data_files('playwright')
datas.append(('geetest/model/triple.onnx', 'geetest/model'))
datas.append(('geetest/model/yolo.onnx', 'geetest/model'))

datas.append((
    os.path.abspath('ms-playwright'),
    'playwright/ms-playwright'
))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    module_collection_mode={
        'gradio': 'py',  # Collect gradio package as source .py files
        'gradio_calendar': 'py',  # Collect'
        'gradio_log': 'py',  # Collect'
    },
    hiddenimports=['geetest.TripleValidator', 'geetest.AmorterValidator', 'bili_ticket_gt_python',
                   'scipy._lib.array_api_compat.numpy.fft'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MUSE-BiliTickets-Buyer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico']
)