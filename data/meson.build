blueprints = custom_target(
  'blueprints',
  input: files(
    'ui/welcome_page.blp',
    'ui/window.blp',
  ),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

gnome.compile_resources(
  'penfold',
  'penfold.gresource.xml',
  dependencies: blueprints,
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

install_subdir(
  'icons/hicolor',
  install_dir: get_option('datadir') / 'icons',
)

install_data(
  f'@app_id@.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas',
)
