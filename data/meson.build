blueprints = custom_target(
  'blueprints',
  input: files(
    'ui/document_header.blp',
    'ui/main_menu.blp',
    'ui/page_entry.blp',
    'ui/welcome_page.blp',
    'ui/window.blp',
    'ui/zoom_controls.blp',
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

i18n.merge_file(
  input: f'@app_id@.desktop.in',
  output: f'@app_id@.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

i18n.merge_file(
  input: f'@app_id@.metainfo.xml.in',
  output: f'@app_id@.metainfo.xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo',
)
