# Contributing

Open an issue with a reproducible example, or submit a pull request against `main`.

Before submitting software changes, run:

```sh
python3 -m unittest discover -s tests -q
python3 wokwi/test_controller.py
python3 scripts/package_release.py
python3 scripts/verify_release.py release/EnergyLine-v1.1.0-final.zip
```

The Arduino controller tests require a C++11 compiler named `c++`. The complete sketch must also be compiled in Wokwi or an Arduino toolchain after firmware changes. Run KiCad DRC/ERC/parity checks and ngspice again after electrical changes; refresh fabrication outputs after copper or drill changes. Consult the component-specific READMEs.

Keep assumed, simulated and physically measured results clearly distinguished. Do not add credentials, runtime databases, personal logs, generated caches or unreviewed manufacturing outputs to a pull request. Preserve third-party notices. Hardware remains an unbuilt engineering prototype until actual assembly and measurements are recorded.
