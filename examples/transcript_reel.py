"""Rebuild the opening SpaceX/Tesla example with local artwork and supplied audio."""

import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from whiteboard_animator import Region, Scene, SnippetRegionPlan, render_video


WIDTH, HEIGHT, FPS = 1080, 1920, 30
INK, BLUE, GOLD, GREEN = "#202c37", "#286e9c", "#c48423", "#34765a"
CAPTIONS = [
    (0, 2, "There's been a lot of reporting"),
    (2, 4, "and anticipation of a merger"),
    (4, 6, "with Tesla."),
    (6, 8, "You may be limited on what you can say."),
    (8, 10, "Taking a step back,"),
    (10, 13, "how do you think about the pros and cons"),
    (13, 15, "of a potential combination?"),
    (15, 17, "As part of that framework,"),
    (17, 19, "are there roadblocks you need to address"),
    (19, 20, "before embarking on it?"),
    (20, 22, "Both SpaceX and Tesla have formed"),
    (22, 25, "special committees to discuss this idea"),
    (25, 27, "at the request of shareholders."),
]


def font(size, bold=False, marker=True):
    candidates = (
        [r"C:\Windows\Fonts\comicbd.ttf", r"C:\Windows\Fonts\comic.ttf"]
        if marker else [r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"]
    )
    candidates.append("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    raise RuntimeError("Install a TrueType font such as DejaVu Sans to render this example")


def label(draw, xy, words, size=48, color=INK, marker=True):
    draw.text(xy, words, font=font(size, bold=True, marker=marker), fill=color, anchor="mm")


def curve(draw, points, color=INK, width=7):
    control = np.asarray(points, dtype=float)
    samples = []
    for t in np.linspace(0, 1, 100):
        point = sum(
            math.comb(len(control) - 1, i) * (1 - t) ** (len(control) - 1 - i)
            * t ** i * p for i, p in enumerate(control)
        )
        samples.append(tuple(point))
    draw.line(samples, fill=color, width=width, joint="curve")


def arrow(draw, points):
    draw.line(points, fill=BLUE, width=7, joint="curve")
    x, y = points[-1]
    px, py = points[-2]
    angle = math.atan2(y - py, x - px)
    draw.line([
        (x - 22 * math.cos(angle - 0.5), y - 22 * math.sin(angle - 0.5)),
        (x, y),
        (x - 22 * math.cos(angle + 0.5), y - 22 * math.sin(angle + 0.5)),
    ], fill=BLUE, width=7)


def people(draw, center, top, count=3):
    for index in range(count):
        x = center + (index - (count - 1) / 2) * 112
        draw.ellipse((x - 25, top, x + 25, top + 55), outline=INK, width=7)
        curve(draw, [(x - 50, top + 135), (x - 48, top + 65),
                     (x + 48, top + 65), (x + 50, top + 135)], BLUE)
        draw.line([(x - 50, top + 135), (x + 50, top + 135)], fill=BLUE, width=7)


def table(draw, center, top):
    people(draw, center, top)
    draw.rounded_rectangle((center - 275, top + 155, center + 275, top + 220),
                           radius=18, outline=INK, width=7)
    for x in (center - 230, center + 230):
        draw.line([(x, top + 225), (x - 10, top + 265)], fill=INK, width=7)


def board(kicker, title):
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    label(draw, (510, 190), kicker, 27, BLUE, marker=False)
    label(draw, (510, 290), title, 69)
    return image, draw


def region(order, start, end, bounds, name):
    x1, y1, x2, y2 = bounds
    return Region(
        label=name, role="main_concept", object=name, expected_visual=name,
        reveal_order=order, start=start, end=end,
        box={"xmin": int(x1 / WIDTH * 1000), "ymin": int(y1 / HEIGHT * 1000),
             "xmax": math.ceil(x2 / WIDTH * 1000), "ymax": math.ceil(y2 / HEIGHT * 1000)},
    )


def storyboard(work):
    scenes = []
    image, draw = board("THE MERGER QUESTION", "SpaceX + Tesla?")
    label(draw, (330, 435), "SpaceX", 60, BLUE)
    curve(draw, [(330, 515), (180, 680), (260, 800)])
    curve(draw, [(330, 515), (480, 680), (400, 800)])
    draw.line([(260, 800), (400, 800)], fill=INK, width=7)
    draw.ellipse((300, 625, 360, 685), outline=BLUE, width=8)
    curve(draw, [(265, 715), (200, 735), (210, 825), (260, 790)], BLUE)
    curve(draw, [(395, 715), (460, 735), (450, 825), (400, 790)], BLUE)
    draw.line([(285, 820), (305, 880), (330, 850), (355, 880), (375, 820)],
              fill=GOLD, width=9, joint="curve")
    label(draw, (690, 945), "Tesla", 60, BLUE)
    curve(draw, [(470, 1150), (440, 1040), (520, 1050), (540, 1050)])
    curve(draw, [(540, 1050), (590, 965), (710, 980), (755, 1055)])
    curve(draw, [(755, 1055), (895, 1070), (890, 1150), (865, 1150)])
    draw.line([(475, 1150), (865, 1150)], fill=INK, width=7)
    draw.line([(555, 1056), (745, 1056)], fill=BLUE, width=6)
    for x in (550, 810):
        draw.ellipse((x - 42, 1115, x + 42, 1199), fill="white", outline=INK, width=8)
    curve(draw, [(530, 685), (850, 620), (850, 820)], BLUE, 6)
    label(draw, (835, 835), "?", 100, BLUE)
    label(draw, (510, 1365), "A potential combination", 42, BLUE)
    plan = SnippetRegionPlan(idea="The merger question", regions=[
        region(1, 0, 0.6, (75, 150, 945, 355), "title"),
        region(2, 0.6, 2.2, (175, 390, 485, 900), "spacex"),
        region(3, 2.2, 3.8, (510, 600, 920, 920), "question"),
        region(4, 4, 5.25, (430, 910, 915, 1220), "tesla"),
        region(5, 5.25, 5.8, (100, 1315, 925, 1420), "potential"),
    ])
    scenes.append((image, 6, plan))

    image, draw = board("THE QUESTIONS", "What's the trade-off?")
    draw.line([(510, 490), (510, 1015)], fill=INK, width=8)
    draw.line([(365, 1020), (655, 1020)], fill=INK, width=8)
    draw.line([(175, 620), (845, 620)], fill=INK, width=8)
    draw.ellipse((490, 600, 530, 640), fill="white", outline=BLUE, width=7)
    for x, color, word in ((285, GREEN, "Pros?"), (735, GOLD, "Cons?")):
        label(draw, (x, 470), word, 63, color)
        draw.line([(x, 628), (x - 108, 850), (x + 108, 850), (x, 628)],
                  fill=color, width=6, joint="curve")
        draw.arc((x - 108, 785, x + 108, 915), 0, 180, fill=color, width=7)
        draw.line([(x - 34, 760), (x + 34, 760)], fill=color, width=9)
        if word == "Pros?":
            draw.line([(x, 726), (x, 794)], fill=color, width=9)
    for points in (
        [(420, 1110), (413, 1165)], [(400, 1270), (390, 1355)],
        [(600, 1110), (607, 1165)], [(620, 1270), (630, 1355)],
    ):
        draw.line(points, fill=BLUE, width=6)
    draw.rounded_rectangle((300, 1180, 720, 1255), radius=8,
                           fill="white", outline=INK, width=7)
    for x in range(320, 650, 66):
        draw.line([(x, 1247), (x + 56, 1188)], fill=GOLD, width=10)
    for x in (350, 670):
        draw.line([(x, 1262), (x, 1330)], fill=INK, width=7)
    label(draw, (510, 1420), "Any roadblocks?", 45)
    plan = SnippetRegionPlan(idea="Pros, cons, and roadblocks", regions=[
        region(1, 0, 0.7, (70, 150, 955, 355), "title"),
        region(2, 1.8, 3.6, (160, 485, 860, 1040), "balance"),
        region(3, 4, 5.25, (170, 415, 410, 525), "pros"),
        region(4, 5.25, 6.7, (610, 415, 870, 525), "cons"),
        region(5, 9.1, 10.3, (380, 1095, 640, 1175), "path"),
        region(6, 11, 12.5, (290, 1175, 730, 1370), "barrier"),
        region(7, 12.5, 13.7, (190, 1380, 835, 1460), "roadblocks"),
    ])
    scenes.append((image, 14, plan))

    image, draw = board("WHAT THE RESPONSE CONFIRMS", "Two committees.")
    label(draw, (510, 440), "SpaceX", 59, BLUE)
    table(draw, 510, 520)
    label(draw, (510, 880), "Tesla", 59, BLUE)
    table(draw, 510, 950)
    people(draw, 510, 1270)
    label(draw, (510, 1470), "Shareholders", 43, BLUE)
    arrow(draw, [(270, 1340), (130, 1340), (130, 675), (200, 675)])
    arrow(draw, [(750, 1340), (890, 1340), (890, 1100), (820, 1100)])
    plan = SnippetRegionPlan(idea="Shareholders request separate committees", regions=[
        region(1, 0, 0.65, (70, 150, 955, 355), "title"),
        region(2, 0.65, 1.25, (280, 390, 750, 490), "spacex-label"),
        region(3, 1.25, 1.9, (280, 830, 750, 930), "tesla-label"),
        region(4, 2, 3.4, (220, 500, 800, 810), "spacex-committee"),
        region(5, 3.4, 4.8, (220, 940, 800, 1235), "tesla-committee"),
        region(6, 5, 6.3, (335, 1250, 690, 1430), "shareholders"),
        region(7, 6.3, 7.1, (110, 650, 210, 1360), "request-spacex"),
        region(8, 7.1, 7.8, (810, 1080, 910, 1360), "request-tesla"),
        region(9, 7.8, 8.5, (255, 1435, 785, 1510), "shareholders-label"),
    ])
    scenes.append((image, 10, plan))
    result = []
    for index, (image, duration, plan) in enumerate(scenes, 1):
        path = work / f"scene-{index:02d}.png"
        image.save(path)
        (work / f"scene-{index:02d}.regions.json").write_text(plan.model_dump_json(indent=2))
        result.append(Scene(path, duration=duration, region_plan=plan))
    return result


def timestamp(seconds):
    return f"0:00:{int(seconds):02d}.00"


def captions(work):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Segoe UI,50,&H00372C20,&H00372C20,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,3,0,2,100,170,235,1
Style: Note,Segoe UI,22,&H006C6258,&H006C6258,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,2,0,2,100,170,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = [header, "Dialogue: 1,0:00:00.00,0:00:30.00,Note,,0,0,0,,Edited excerpt | Supplied narration"]
    caption_font = font(50, marker=False)
    for start, end, words in CAPTIONS:
        lines, current = [], ""
        for word in words.split():
            trial = f"{current} {word}".strip()
            if caption_font.getlength(trial) > 780 and current:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
        if len(lines) > 2:
            raise ValueError(f"Caption needs more than two lines: {words}")
        rows.append(f"Dialogue: 0,{timestamp(start)},{timestamp(end)},Caption,,0,0,0,,"
                    + r"\N".join(lines))
    (work / "captions.ass").write_text("\n".join(rows) + "\n", encoding="utf-8")


def peak_memory_mb():
    if os.name != "nt":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            )
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    get_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_info.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not get_info(
        handle, ctypes.byref(counters), ctypes.sizeof(counters),
    ):
        raise OSError("Could not measure process memory")
    return round(counters.PeakWorkingSetSize / 1024 ** 2, 1)


def export_video(silent, audio, target, work):
    base = "atrim=duration=27,apad,atrim=duration=30"
    analysis = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(audio.resolve()), "-vn", "-af",
        base + ",loudnorm=I=-16:TP=-3:LRA=11:print_format=json", "-f", "null", "-",
    ], capture_output=True, text=True, check=True)
    levels, _ = json.JSONDecoder().raw_decode(analysis.stderr[analysis.stderr.rfind("{"):])
    if not math.isfinite(float(levels["input_i"])):
        raise ValueError("Narration must contain audible speech")
    normalization = (
        "loudnorm=I=-16:TP=-3:LRA=11"
        f":measured_I={levels['input_i']}:measured_TP={levels['input_tp']}"
        f":measured_LRA={levels['input_lra']}:measured_thresh={levels['input_thresh']}"
        f":offset={levels['target_offset']}:linear=true"
    )
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio.resolve()),
        "-vf", "ass=captions.ass", "-af",
        base + "," + normalization
        + ",aresample=48000,alimiter=limit=0.707946:level=false:latency=true",
        "-map", "0:v:0", "-map", "1:a:0", "-t", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-movflags", "+faststart", str(target),
    ], cwd=work, check=True)
    print(f"Created {target}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True, help="a 30-second narration file")
    parser.add_argument("--comparison-audio", type=Path, help="optional same-story narration for A/B comparison")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    captions(work)
    scenes = storyboard(work)
    start, cpu_start = time.monotonic(), time.process_time()
    silent = work / "silent.mp4"
    render_video(scenes, silent, quality="high", output_size=(WIDTH, HEIGHT), fps=FPS)
    render_seconds = time.monotonic() - start
    cpu_seconds = time.process_time() - cpu_start
    exports = [(args.audio, output)]
    if args.comparison_audio:
        exports.append((args.comparison_audio, output.with_stem(output.stem + "-same-voice")))
    for audio, target in exports:
        export_video(silent, audio, target, work)
    report = {
        "native_size": [WIDTH, HEIGHT], "fps": FPS, "render_seconds": round(render_seconds, 2),
        "python_cpu_seconds": round(cpu_seconds, 2),
        "python_peak_working_set_mb": peak_memory_mb(),
        "notes": "No image upscaling; pixel-based brush defaults retained. No speech model installed.",
    }
    (work / "benchmark.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
