# PyInstaller hooks for open-daily-stock
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules('data_provider')
