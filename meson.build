project(
  'penfold',
  version: '1.0.0-alpha.1',
  meson_version: '>= 1.7.0',
  license: 'GPL-3.0-only',
  default_options: ['warning_level=2', 'werror=true'],
)

app_id = 'io.github.ibanurq.Penfold'
resource_prefix = '/io/github/ibanurq/Penfold'

gnome = import('gnome')
i18n = import('i18n')
python = import('python')

python_installation = python.find_installation('python3')
pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
localedir = get_option('prefix') / get_option('localedir')

subdir('data')
subdir('penfold')
subdir('po')

gnome.post_install(glib_compile_schemas: true)
