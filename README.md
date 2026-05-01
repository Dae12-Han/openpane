# openpane 🌸

> Open the pane. See the world beyond your terminal.

You've been coding so hard you forgot the outside world exists.  
**openpane sets your terminal background to match the real weather outside.**

```bash
pip install openpane
openpane on
```

That's it. Your terminal becomes a window — and you can keep coding right through it.

---

## How it works

`openpane on` does four things:

1. Detects your location via IP
2. Fetches real-time weather from Open-Meteo
3. Generates a matching background image (cached after the first run)
4. Applies it as your terminal's background

You keep typing, running commands, and coding as usual.  
The window is just... there. Like a real one.

| Outside | Background |
|---------|------------|
| Spring, clear | Cherry blossoms 🌸 |
| Rain | Falling raindrops 🌧 |
| Snow | Drifting snowflakes ❄️ |
| Clear day | Soft clouds ☁️ |
| Night | Twinkling stars ✦ |

---

## Supported terminals

| OS | Terminal | Animation |
|----|----------|-----------|
| macOS | [iTerm2](https://iterm2.com) | ✅ animated GIF |
| Windows | [Windows Terminal](https://aka.ms/terminal) | static PNG (Windows Terminal does not animate GIFs) |

> Linux support is on the roadmap.  
> macOS Terminal.app is **not** supported — it does not allow background images.

---

## Install

```bash
pip install openpane
```

That installs Pillow as a dependency for image generation.  
No API keys. No config files. No setup.

---

## Usage

```bash
openpane on            # apply weather background
openpane off           # remove background
openpane doctor        # diagnose your environment
openpane clear-cache   # regenerate images on next run
```

---

## Why pip?

Because installing a desktop ambient tool with one shell command feels right.  
Because the prompt is the developer's home, and `pip install` is the doormat.

---

## Roadmap

- [ ] Linux terminal support
- [ ] Custom city override (`openpane on --city Tokyo`)
- [ ] More seasonal effects (autumn leaves, summer fireflies)
- [ ] Time-based transitions (dawn → day → dusk → night)
- [ ] User-supplied custom backgrounds

---

## Contributing

PRs welcome. If you want to add a new effect, a new platform, or fix a bug —  
open an issue or send a pull request.

---

## License

MIT
