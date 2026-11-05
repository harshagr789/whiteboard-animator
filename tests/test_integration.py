"""Real model, installed CLI, ffmpeg, and decoded-output checks (no mocks)."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sysconfig
import wave

import cv2
import numpy as np
from PIL import Image
import pytest

from whiteboard_animator.craft_detector import CRAFTDetector
from whiteboard_animator.video_encoding import encode_blank_video


pytestmark = pytest.mark.integration
BUNDLED_MODEL = Path(__file__).resolve().parents[1] / "whiteboard_animator/models/craft.onnx"


@pytest.fixture(autouse=True)
def require_media_tools():
    missing = [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]
    if missing:
        pytest.skip(f"integration tests require {', '.join(missing)} on PATH")


@pytest.fixture
def scene(tmp_path):
    image = np.full((320, 640, 3), 255, dtype=np.uint8)
    cv2.putText(image, "SUN", (220, 90), cv2.FONT_HERSHEY_SIMPLEX, 2, (20, 20, 20), 4)
    cv2.circle(image, (320, 220), 60, (230, 150, 20), -1)
    path = tmp_path / "scene.png"
    Image.fromarray(image).save(path)
    return path, image


def run_cli(*args):
    # Use the installed console script beside this interpreter, including on Windows.
    executable = Path(sysconfig.get_path("scripts")) / ("whiteboard-animate.exe" if os.name == "nt" else "whiteboard-animate")
    env = {**os.environ, "CRAFT_MODEL_PATH": str(BUNDLED_MODEL)}
    result = subprocess.run(
        [str(executable), *map(str, args)], capture_output=True, text=True,
        env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "CRAFT unavailable" not in result.stderr
    return result


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)


def frames(path, width=640, height=320):
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=30,
    )
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, height, width, 3)


def test_bundled_craft_detects_text(scene):
    _, source = scene
    mask = CRAFTDetector(model_path=str(BUNDLED_MODEL)).detect(source)
    text_ink = np.any(source[:110] < 240, axis=2)
    assert mask.dtype == bool and mask.shape == source.shape[:2]
    assert mask[:110][text_ink].mean() > 0.5
    assert mask[:30].mean() < 0.1


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "P", "L"])
def test_cli_encodes_progressive_reveal_and_final_image(scene, tmp_path, mode):
    path, source = scene
    image = Image.fromarray(source)
    if mode == "RGBA":
        # Hidden black pixels must be composited onto white, not revealed as ink.
        rgba = np.zeros((*source.shape[:2], 4), dtype=np.uint8)
        ink = np.any(source < 240, axis=2)
        rgba[ink, :3] = source[ink]
        rgba[ink, 3] = 255
        image = Image.fromarray(rgba)
    elif mode == "P":
        image = image.convert("P", palette=Image.Palette.ADAPTIVE)
        source = np.array(image.convert("RGB"))
    elif mode == "L":
        image = image.convert("L")
        source = np.array(image.convert("RGB"))
    image.save(path)
    output = tmp_path / "reveal.mp4"
    run_cli(path, "--duration", "4", "--quality", "low", "-v", "-o", output)
    metadata = probe(output)
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (640, 320)
    assert video["codec_name"] == "h264"
    assert video["avg_frame_rate"] == "20/1"
    assert abs(float(metadata["format"]["duration"]) - 4) <= 0.1
    decoded = frames(output)
    assert decoded[0].mean() > 254
    ink_counts = np.any(decoded < 200, axis=3).sum(axis=(1, 2))
    assert 0 < ink_counts[20] < ink_counts[-1] * 0.9
    source_ink = np.any(source < 200, axis=2)
    error = np.abs(decoded[-1].astype(float) - source.astype(float))
    assert error[source_ink].mean() < 15
    assert np.abs(decoded[-1].astype(float) - decoded[-10].astype(float)).mean() < 1


def test_cli_concatenates_narrated_scenes_with_region_plans(scene, tmp_path):
    path, _ = scene
    audio = tmp_path / "narration.wav"
    rate = 16000
    samples = (np.sin(2 * np.pi * 440 * np.arange(rate * 3) / rate) * 4000).astype("<i2")
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())
    plan = tmp_path / "scene.regions.json"
    plan.write_text(json.dumps({
        "idea": "The sun", "regions": [{
            "label": "sun", "role": "main_concept", "object": "sun and label",
            "reveal_order": 1, "expected_visual": "sun and label", "annotation": "The sun shines.",
            "box": {"ymin": 0, "xmin": 0, "ymax": 1000, "xmax": 1000},
        }],
    }))
    output = tmp_path / "lecture.mp4"
    run_cli(path, path, "--audio", audio, audio, "--regions", plan, plan, "-o", output)
    metadata = probe(output)
    assert {s["codec_type"] for s in metadata["streams"]} == {"video", "audio"}
    assert abs(float(metadata["format"]["duration"]) - 6) < 0.2
    decoded = frames(output)
    assert decoded[0].mean() > 254
    assert np.any(decoded[-1] < 200, axis=2).sum() > 10000
    decoded_audio = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-f", "s16le", "-ac", "1", "-ar", str(rate), "-"],
        check=True, capture_output=True, timeout=30,
    )
    waveform = np.frombuffer(decoded_audio.stdout, dtype="<i2")
    assert 5.8 < len(waveform) / rate < 6.2
    assert np.abs(waveform.astype(float)).mean() > 1000


def test_encoder_failure_includes_ffmpeg_diagnostic(tmp_path):
    with pytest.raises(RuntimeError, match="ffmpeg failed") as error:
        encode_blank_video(64, 64, 2, str(tmp_path / "missing" / "out.mp4"), 20, "500k", "veryfast")
    assert "No such file or directory" in str(error.value)
    assert "libx264" in str(error.value)


def decoded_frame(path, seconds):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, bgr = cap.read()
        assert ok, f"could not decode frame at {seconds}s"
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    finally:
        cap.release()


def write_timed_plan(path, regions):
    path.write_text(json.dumps({
        "idea": "timed reveal",
        "regions": [
            {"label": f"r{i}", "role": "main_concept", "reveal_order": i,
             "expected_visual": "drawing", "box": box, "start": start, "end": end}
            for i, (box, start, end) in enumerate(regions, 1)
        ],
    }))


def test_cli_native_portrait_with_delayed_cue(tmp_path):
    source = np.full((1920, 1080, 3), 255, dtype=np.uint8)
    cv2.putText(source, "SUN", (320, 600), cv2.FONT_HERSHEY_SIMPLEX, 4, (20, 20, 20), 8)
    cv2.circle(source, (540, 1000), 120, (230, 150, 20), -1)
    image = tmp_path / "portrait.png"
    Image.fromarray(source).save(image)
    plan = tmp_path / "timed.json"
    write_timed_plan(plan, [
        ({"ymin": 0, "xmin": 0, "ymax": 1000, "xmax": 1000}, 0.5, 1.6),
    ])
    output = tmp_path / "native.mp4"
    run_cli(image, "--regions", plan, "--duration", "2", "--quality", "high",
            "--size", "1080x1920", "--fps", "30", "-o", output)
    metadata = probe(output)
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert (stream["width"], stream["height"]) == (1080, 1920)
    assert stream["avg_frame_rate"] == "30/1"
    assert abs(float(metadata["format"]["duration"]) - 2) <= 1 / 30
    assert decoded_frame(output, 0.4).mean() > 254
    final = decoded_frame(output, 1.9)
    ink = np.any(source < 200, axis=2)
    assert np.abs(final.astype(float) - source.astype(float))[ink].mean() < 15


def test_cli_letterboxes_timed_regions_across_multiple_scenes(scene, tmp_path):
    image, _ = scene
    plan = tmp_path / "timed.json"
    write_timed_plan(plan, [
        ({"ymin": 0, "xmin": 0, "ymax": 350, "xmax": 1000}, 0.2, 0.8),
        ({"ymin": 350, "xmin": 0, "ymax": 1000, "xmax": 1000}, 1.1, 1.7),
    ])
    output = tmp_path / "fitted.mp4"
    run_cli(image, image, "--regions", plan, plan, "--duration", "2",
            "--size", "360x640", "--fps", "30", "-o", output)
    metadata = probe(output)
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert (stream["width"], stream["height"]) == (360, 640)
    assert stream["avg_frame_rate"] == "30/1"
    assert abs(float(metadata["format"]["duration"]) - 4) <= 0.1
    middle = decoded_frame(output, 0.95)
    assert middle[:230].mean() > 254 and middle[410:].mean() > 254
    assert np.any(middle[250:290] < 200, axis=2).sum() > 100
    assert middle[320:390].mean() > 254
    assert decoded_frame(output, 2.1).mean() > 254
    assert np.any(decoded_frame(output, 3.9)[320:390] < 200, axis=2).sum() > 100
