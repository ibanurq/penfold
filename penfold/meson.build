launcher_data = configuration_data()
launcher_data.set('PYTHON', python_installation.full_path())
launcher_data.set('PKGDATADIR', pkgdatadir)
launcher_data.set('LOCALEDIR', localedir)

configure_file(
  input: 'penfold.in',
  output: 'penfold',
  configuration: launcher_data,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

# Every module is listed so that nothing else from the source tree (such as caches) gets installed.
# tests/test_build.py checks that no module is missing from these lists.
install_data(
  '__init__.py',
  'application.py',
  'config.py',
  'errors.py',
  'main.py',
  install_dir: pkgdatadir / 'penfold',
)

subdir('document')
subdir('rendering')
subdir('ui')
