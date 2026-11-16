# omakodi

[![Built for Omarchy: Plugin](https://raw.githubusercontent.com/tcballard/omarchy-badges/75975e5b5bf75e7ede3764bcd2950046f7abfe2c/badges/v1/omarchy-plugin.svg)](https://github.com/tcballard/omarchy-badges)

A keyboard remote for Kodi: send links to play or queue, drive Kodi's menus from the keyboard, and see what is playing in the bar.

Kinds: service, bar-widget, panel

## GitHub topics

Pair this badge with `omarchy` and `omarchy-plugin` in your GitHub repository's
About topics. The badge does not set topics automatically. Keep other relevant
topics too. This is a community discovery convention, not marketplace approval.

## Requirements

- Omarchy 4 with Quattro shell-plugin support.
- No additional package, authentication, or privileged setup is required by the
  generated baseline. Document every dependency before release.

## Installation

```bash
omarchy plugin add https://github.com/frestina/omakodi.git --enable
```

For a local checkout:

```bash
omarchy plugin add "$(pwd)" --enable
```

## Validation and tests

```bash
./tests/run
omarchy plugin validate .
```

## Update

```bash
omarchy plugin update io.github.frestina.omakodi
```

## Removal

```bash
omarchy plugin remove io.github.frestina.omakodi
```

The generated baseline stores no data outside normal Omarchy shell
configuration. Update this section when the plugin gains durable state or an
external dependency.

## Security

Omarchy plugins run as unsandboxed code inside `omarchy-shell`. Review this
repository and its dependencies before enabling it.

## License

MIT © 2026 Frestina
