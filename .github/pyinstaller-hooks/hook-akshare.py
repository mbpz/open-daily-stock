from PyInstaller.utils.hooks import collect_data_files

# Collect akshare data files (like calendar.json)
datas = collect_data_files('akshare', include_py_files=True)