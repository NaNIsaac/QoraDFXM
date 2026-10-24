# README media

`logo.png` and `logo_on_dark.png` are 192 px wide copies of `src/qoradfxm/gui/assets/logo_full.png`
and `logo_full_on_dark.png` (the app keeps the full-size files), for the README's 96 px logo:

```sh
uv run --no-project --with pillow python -c "from PIL import Image
for s, d in [('logo_full', 'logo'), ('logo_full_on_dark', 'logo_on_dark')]:
    im = Image.open(f'src/qoradfxm/gui/assets/{s}.png').convert('RGBA')
    im = im.resize((192, round(im.height * 192 / im.width)), Image.Resampling.LANCZOS)
    im.quantize(128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(f'docs/media/{d}.png', optimize=True)"
```
