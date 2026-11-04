# Third-party notes

This source repository contains the goose-log library, examples, tests, scripts,
and documentation under the [Apache License 2.0](LICENSE). No third-party source
trees, compiled dependencies, or compiler binaries are bundled in its tracked
files. The library's runtime uses Goose's language/runtime facilities; examples
and tests also import Goose standard-library modules.

`make setup` separately downloads the [Goose compiler](https://github.com/aardappel/goose)
at the full commit in `GOOSE_REVISION`. Its repository has its own Apache-2.0
LICENSE and includes third-party components with their own terms, including
TinyCC's LGPL-2.1 COPYING file. Their notices remain in the downloaded source
tree. Do not treat the complete downloaded toolchain as uniformly Apache-only.

The downloaded `.toolchain/` and generated `.build/` directories are ignored and
are not part of this source publication. Anyone separately redistributing a
compiler binary, runtime bundle, or other dependency should inspect and preserve
the notices and terms applicable to that artifact. GCC, Clang, Python, CMake,
Git, Make, and GitHub Actions are external development tools, not vendored here.

The optional `bench/compare/run.py` comparison fetches pinned copies of
[rxi/log.c](https://github.com/rxi/log.c) (MIT),
[spdlog](https://github.com/gabime/spdlog) (MIT, with bundled fmt notices), and
[Macho0x/goose-logger](https://github.com/Macho0x/goose-logger) (Apache-2.0)
into ignored `.build/compare/` directories. Their complete license files stay
with the downloaded sources. They are comparison-only dependencies, not imports
of the goose-log library. The matched-policy benchmark deliberately calls the
third-party Goose timestamp formatter/redactor on both paths; it does not
relicense those sources or make their automatic policy part of goose-log.

The optional UTC example, its tests and component benchmark import
[goose-time](https://github.com/carabistouflette/goose-time) at
`343887caeee0a1f4e2e536ff322fcafb454e11bd` (Apache-2.0). Goose fetches that
source into its package cache; the source is not bundled here. Its LICENSE and
notices remain in the fetched repository. It is not a dependency of logger.goose
or the standard core test targets.
