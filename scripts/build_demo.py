"""Render a captioned 120-second MP4 from saved numerical results and cell traces.
Requires Pillow and ffmpeg; no screenshots, synthetic hardware footage or network calls.
"""

import json, math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, DURATION = 1280, 720, 12, 120
BG = "#f5f5ed"
INK = "#213d31"
GREEN = "#567d55"
ORANGE = "#c87942"
MUTED = "#71836b"
PALE = "#dfe8d4"
FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
if not FONT.exists():
    FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def font(size):
    return ImageFont.truetype(str(FONT), size)


F = {s: font(s) for s in (14, 18, 20, 22, 24, 28, 32, 38, 44, 52, 66)}


def txt(draw, xy, value, size=24, color=INK):
    draw.text(xy, str(value), font=F[size], fill=color)


def box(draw, xy, fill=PALE):
    draw.rounded_rectangle(xy, radius=12, fill=fill)


def base(t, kicker, title, subtitle):
    image = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(image)
    txt(d, (48, 25), "E ↗  EnergyLine", 24)
    txt(d, (840, 32), "SOFTWARE-ONLY ENGINEERING STUDY", 14, MUTED)
    d.line((48, 74, 1232, 74), fill="#d4decb", width=2)
    txt(d, (48, 103), kicker, 18, ORANGE)
    txt(d, (48, 141), title, 44)
    txt(d, (48, 204), subtitle, 22, MUTED)
    d.line((48, 667, 1232, 667), fill="#d4decb", width=2)
    txt(
        d,
        (48, 682),
        "Synthetic inputs · Simulated results · No physical hardware validation",
        18,
        MUTED,
    )
    txt(d, (1115, 682), f"{int(t):03d} / 120 s", 14, MUTED)
    d.rectangle((48, 654, 48 + int(1184 * t / DURATION), 657), fill=ORANGE)
    return image, d


def cell_view(d, frame):
    ox, oy = 74, 275
    box(d, (ox, oy, ox + 695, oy + 330), "#e6ecde")
    d.rectangle(
        (ox + 90, oy + 62, ox + 610, oy + 240),
        fill="#b9c9ab",
        outline="#597751",
        width=3,
    )
    if frame["signals"]["part_present"]:
        d.rectangle(
            (ox + 160, oy + 92, ox + 540, oy + 210),
            fill="#90aa7d",
            outline=GREEN,
            width=2,
        )
        for j in range(4):
            d.rectangle(
                (ox + 176 + j * 90, oy + 105, ox + 243 + j * 90, oy + 196),
                fill="#4f7352",
            )
        if frame["signals"]["cover_present"]:
            d.rectangle(
                (ox + 160, oy + 92, ox + 540, oy + 210), outline="#d0dfbf", width=8
            )
            txt(d, (ox + 249, oy + 138), "ENERGYLINE", 28, "#edf3e6")
    p = frame["equipment"]["clamp_position"] * 26
    box(d, (ox + 100 + p, oy + 128, ox + 158 + p, oy + 176), ORANGE)
    box(d, (ox + 542 - p, oy + 128, ox + 600 - p, oy + 176), ORANGE)
    txt(d, (ox + 20, oy + 274), frame["controller_state"], 28, INK)
    txt(d, (ox + 440, oy + 281), f"Cell time {frame['timestamp_s']:.2f} s", 18, MUTED)
    x = 815
    y = 278
    for key in (
        "part_present",
        "clamp_closed",
        "process_done",
        "safety_permit",
        "communication_ok",
    ):
        color = GREEN if frame["signals"][key] else "#cbd6c1"
        d.ellipse((x, y + 5, x + 14, y + 19), fill=color)
        txt(d, (x + 28, y), key, 20)
        y += 39
    y += 12
    txt(
        d,
        (x, y),
        "Motion: " + ("enabled" if frame["outputs"]["motion_enable"] else "inhibited"),
        22,
        ORANGE,
    )
    y += 39
    txt(d, (x, y), "Process result: " + frame["result"], 20)


def main():
    media = ROOT / "media"
    media.mkdir(exist_ok=True)
    report = json.loads((ROOT / "results/economics/comparison.json").read_text())
    cases = {c["id"]: c for c in report["cases"]}
    normal = json.loads((ROOT / "results/s3_commissioning/normal.json").read_text())
    fault = json.loads(
        (ROOT / "results/s3_commissioning/permit_removed.json").read_text()
    )
    chapters = [
        (0, 15, "Define the system"),
        (15, 30, "Find the constraint"),
        (30, 48, "Compare alternatives"),
        (48, 65, "Commission a normal cycle"),
        (65, 90, "Fault, reset and recovery"),
        (90, 108, "Balance cost and reliability"),
        (108, 120, "State the evidence boundary"),
    ]
    captions = []
    for i, (a, b, label) in enumerate(chapters, 1):

        def stamp(value):
            return f"00:{int(value)//60:02d}:{int(value)%60:02d},000"

        captions.append(
            f"{i}\n{stamp(a)} --> {stamp(b)}\n{label} — software simulation with synthetic inputs\n"
        )
    (media / "demo.srt").write_text("\n".join(captions))
    log = (ROOT / "work/video_render.log").open("w")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(media / "EnergyLine_demo.mp4"),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
    thumbs = []
    for frame_number in range(FPS * DURATION):
        t = frame_number / FPS
        if t < 15:
            image, d = base(
                t,
                "01 / REQUIREMENTS",
                "An assembly system, before buying equipment.",
                "Five operations. One inert mock module. A clear production boundary.",
            )
            for i, label in enumerate(
                (
                    "Identify tray",
                    "Load inserts",
                    "Cover & fasten",
                    "Inspect & test",
                    "Label & release",
                )
            ):
                x = 48 + i * 242
                box(d, (x, 290, x + 220, 420))
                txt(d, (x + 18, 308), f"S{i+1}", 32, GREEN)
                txt(d, (x + 18, 369), label, 20)
            txt(d, (48, 470), "240 good units / shift", 44)
            txt(
                d,
                (48, 536),
                "25,200 production seconds ÷ 240 = 105-second demand takt",
                28,
                MUTED,
            )
        elif t < 30:
            image, d = base(
                t,
                "02 / BASELINE",
                "S3 is the first constraint. S2 is next.",
                "Assumed manual times: 45 / 120 / 150 / 90 / 60 seconds.",
            )
            for i, value in enumerate((45, 120, 150, 90, 60)):
                x = 75 + i * 235
                h = value * 1.65
                d.rectangle(
                    (x, 565 - h, x + 150, 565), fill=ORANGE if i in (1, 2) else GREEN
                )
                txt(d, (x, 582), f"S{i+1} · {value}s", 24)
                txt(d, (x + 30, 535 - h), value, 22)
            txt(
                d,
                (48, 248),
                "Ideal deterministic reference: 165 completed units in an empty-start shift.",
                22,
            )
        elif t < 48:
            image, d = base(
                t,
                "03 / ALTERNATIVES",
                "Two manual S3 fixtures: 201 units per shift.",
                "200 paired shifts per comparison; shared staffing and finite buffers.",
            )
            entries = [
                ("Manual, 4 production operators", 163.43),
                ("Two manual S3 fixtures, same staff", 200.505),
                (
                    "Faster S2/S3, 4 production operators",
                    cases["s2_s3_4"]["mean_good_units"],
                ),
            ]
            for i, (label, value) in enumerate(entries):
                y = 285 + i * 110
                txt(d, (48, y), label, 24)
                d.rectangle(
                    (48, y + 39, 48 + value * 3.8, y + 70),
                    fill=GREEN if i == 2 else ORANGE,
                )
                txt(d, (1065, y + 35), f"{value:.1f}", 28)
            txt(
                d,
                (48, 622),
                "All shown configurations also use one dedicated rework operator.",
                20,
                MUTED,
            )
        elif t < 65:
            image, d = base(
                t,
                "04 / CELL ENGINEERING",
                "S3 controller and equipment simulation.",
                "Normal cycle: clamp → process → latch result → transfer → one completion.",
            )
            position = min(
                len(normal["timeline"]) - 1,
                int((t - 48) / 17 * len(normal["timeline"])),
            )
            cell_view(d, normal["timeline"][position])
            txt(
                d,
                (48, 622),
                "Accelerated illustrative cell seconds; not a measured production cycle.",
                20,
                MUTED,
            )
        elif t < 90:
            image, d = base(
                t,
                "05 / COMMISSIONING",
                "Fault recovery requires a separate motion command.",
                "Permit loss → fault → reset acknowledgement → explicit recovery → quarantine.",
            )
            position = min(
                len(fault["timeline"]) - 1, int((t - 65) / 25 * len(fault["timeline"]))
            )
            f = fault["timeline"][position]
            cell_view(d, f)
            txt(
                d,
                (48, 622),
                "11/11 commissioning cases pass. Faulted uncertain units produce no completion.",
                20,
                MUTED,
            )
        elif t < 108:
            image, d = base(
                t,
                "06 / ECONOMICS",
                "Cost and attainment by staffing level.",
                "Faster S2/S3 with identical assumed machine and quality inputs.",
            )
            for i, key in enumerate(("s2_s3_3", "s2_s3_4")):
                c = cases[key]
                x = 48 + i * 610
                box(d, (x, 280, x + 570, 578))
                txt(
                    d,
                    (x + 24, 302),
                    f"{c['production_operators']} production + 1 rework operators",
                    28,
                )
                txt(
                    d,
                    (x + 24, 365),
                    f"{c['demand_attainment']['240']['successful_shifts']} / 200 shifts met 240",
                    32,
                )
                v = c["cost_sensitivity"]["base"][
                    "pooled_conversion_cost_per_good_unit_eur"
                ]
                txt(d, (x + 24, 422), f"EUR {v:.2f} conversion cost / good unit", 24)
                bound = c["demand_attainment"]["240"]["wilson_95_lower"] * 100
                txt(
                    d,
                    (x + 24, 478),
                    f"95% lower attainment bound: {bound:.1f}%",
                    24,
                    ORANGE,
                )
            txt(
                d,
                (48, 622),
                "Costs are hypothetical, exclude good-unit BOM, and do not establish payback.",
                20,
                MUTED,
            )
        else:
            image, d = base(
                t,
                "07 / EVIDENCE & LIMITATIONS",
                "Source, results and verification evidence.",
                "n8n workflows · traceability · scenario evidence · fixture and layout concepts",
            )
            bullets = [
                "Controller outcomes are linked to unit-level line simulation.",
                "Editable concept CAD and a documented tolerance stack are included.",
                "Measurements, supplier quotes and hardware validation remain absent.",
                "No claim of deployed industrial equipment or certified machinery safety.",
            ]
            for i, line in enumerate(bullets):
                txt(d, (62, 282 + i * 67), "• " + line, 24)
            txt(
                d,
                (62, 576),
                "Run the tests. Reproduce the evidence. Inspect the assumptions.",
                28,
                GREEN,
            )
        if frame_number in (6 * FPS, 22 * FPS, 39 * FPS, 57 * FPS, 77 * FPS, 99 * FPS):
            thumbs.append(image.copy())
            image.save(media / f"preview_{int(t):03d}.png")
        process.stdin.write(image.tobytes())
    process.stdin.close()
    code = process.wait()
    log.close()
    if code:
        raise SystemExit(f"ffmpeg failed: {code}")
    sheet = Image.new("RGB", (960, 810), BG)
    for i, im in enumerate(thumbs):
        im.thumbnail((480, 270))
        sheet.paste(im, ((i % 2) * 480, (i // 2) * 270))
    sheet.save(media / "contact_sheet.png")
    (media / "chapters.json").write_text(
        json.dumps(
            [{"start_s": a, "end_s": b, "title": title} for a, b, title in chapters],
            indent=2,
        )
        + "\n"
    )
    print(
        "Rendered captioned 120-second MP4 from recorded cell traces and numerical evidence."
    )


if __name__ == "__main__":
    main()
