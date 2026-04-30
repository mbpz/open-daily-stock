# PyInstaller hooks for open-daily-stock
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('textual')
hiddenimports = collect_submodules('textual')
hiddenimports += collect_submodules('data_provider')
