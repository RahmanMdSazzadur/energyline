# Demonstration media

`EnergyLine_demo.mp4` is a 120-second, 1280×720 H.264 silent, captioned demonstration rendered from actual numerical result files and recorded software cell traces. It is not physical-equipment footage or a browser screen recording. `demo.srt` and `chapters.json` document chapters. On-screen labels explain synthetic inputs, cost exclusions and hardware limitations.

Optional reproduction: install `requirements-media.txt`, ensure ffmpeg and a TrueType font (Arial on macOS or DejaVu Sans on Linux) are available, then run `python3 scripts/build_demo.py`. Pillow 13.0.0 and the installed ffmpeg were used for this release. Normal application operation does not require these media tools.

`contact_sheet.png` and `verified_fault_frame.png` support visual quality review. Encoding and font differences may change video bytes across environments even when numerical results match.
