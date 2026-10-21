# Synthetic ring fit

A known ellipse and ring are drawn into a noisy shot in the beamline HDF5 layout, and the
command line a user runs (`qoradfxm fit`, `qoradfxm ring`) measures them. This shows what the fit
and the ring profile recover, and how the reported fit error relates to the picking error, on data
whose answer is known. No measured data is needed.

```bash
uv run python examples/synthetic_ring_fit/run.py      # prints the result next to the truth, writes result.json
uv run pytest -q tests/test_example_synthetic_ring_fit.py
```

## What it does

1. **Shot.** The ring of `examples/synthetic_ring.py`: a Gaussian ring (width 0.05 in k) on an
   ellipse with centre (200, 150) px, semi-axes 120 and 60 px and tilt 30 degrees, in a 400 x 300
   image with a floor of 5 counts. A dark level of 40 counts with Gaussian read noise (sigma 3) is
   added to the image, and an independent dark frame of the same level is stored in `/dark`. One
   shot with the ring at k = 1.3 and one at k = 1.4. Seed 2026.
2. **Picking.** 200 points on the ellipse, with Gaussian jitter of 0, 0.25, 0.5 and 1 px added to
   both coordinates. The points of `synthetic_ring.ellipse_points` are rounded to 0.01 px, so
   "0" still carries that rounding.
3. **Fit.** `qoradfxm fit SHOT --dataset ... --op sub_bg:/dark --points pts.json --out fit.csv`
   for each jitter.
4. **Ring.** `qoradfxm ring SHOT --dataset ... --points pts.json --k 0.5:2.0:0.01`, with and
   without `--op sub_bg:/dark`, on both shots.

## Result at seed 2026

| jitter (px) | centre x | centre y | major | minor | angle (deg) | fit_error | expected |
|---|---|---|---|---|---|---|---|
| 0 | 200.000 | 150.000 | 239.998 | 120.001 | 30.000 | 0.003 | 0 |
| 0.25 | 200.022 | 150.000 | 239.991 | 120.038 | 29.970 | 0.230 | 0.247 |
| 0.5 | 200.036 | 149.966 | 239.952 | 119.833 | 29.931 | 0.476 | 0.494 |
| 1 | 200.021 | 149.993 | 240.103 | 119.949 | 29.952 | 0.958 | 0.987 |

Truth: centre (200, 150), diameters 240 and 120, 30 degrees. `expected` is
sigma sqrt(1 - 5/N) for N = 200 points and 5 conic parameters.

Ring profile: the peak is at k = 1.30 and 1.40 on the two shots, with and without dark
subtraction. The mean inside the ring (k < 0.9) is 5.01 counts with `sub_bg:/dark` (the floor) and
45.02 without (floor plus dark level).

The fit error reads 3 to 7 % below sigma sqrt(1 - 5/N) at this seed, inside the 15 % tolerance.
The Sampson distance is a first-order approximation of the geometric distance, and one seed does
not separate that from scatter.

## What the test checks

`expected.json` holds two sets of numbers:

- **`truth`**, with a tolerance for each value: centre within 3 standard errors
  (2 sigma / sqrt(N) each, at least 0.01 px), diameters within twice that, angle within 0.2 sigma
  degrees (at least 0.01), fit_error within 15 % of sigma sqrt(1 - 5/N); ring peak within 0.02 of
  the drawn k, mean inside the ring within 1 count of 5 (dark subtracted) or 45 (not subtracted).
  A test also checks that the truth is the geometry the example draws.
- **`regression`**: today's values at seed 2026, so any change in the fit or the profile shows up.

It also checks that the fit error grows with the jitter and that dark subtraction lowers the
profile by the dark level without moving the peak.

## Limitations

- Synthetic data. A clean Gaussian ring on a flat floor; no texture, no partial ring, no detector
  gaps or saturation, no ring that leaves the image on one side only.
- The points are picked from the true ellipse with Gaussian jitter. A person picking on the image
  makes correlated, not independent, errors, which this does not model.
- One seed, one ellipse. The tolerances for the angle and the diameters are rules of thumb, not
  derived standard errors.
