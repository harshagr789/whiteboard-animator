import pytest
from PIL import Image

from whiteboard_animator import cli


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "scene.png"
    Image.new("RGB", (64, 64), "white").save(path)
    return path


def run_cli(image_path, tmp_path, *args):
    return cli.main([str(image_path), "-o", str(tmp_path / "out.mp4"), *args])


@pytest.mark.parametrize("duration", ["0", "-1", "nan", "inf"])
def test_invalid_duration_fails_before_render(image_path, tmp_path, capsys, duration):
    assert run_cli(image_path, tmp_path, f"--duration={duration}") == 1
    assert "--duration must be a finite number greater than zero" in capsys.readouterr().err
    assert not (tmp_path / "out.mp4").exists()


def test_missing_ffmpeg_has_install_hint(image_path, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    assert run_cli(image_path, tmp_path) == 1
    error = capsys.readouterr().err
    assert "ffmpeg not found on PATH" in error
    assert "brew install ffmpeg" in error
    assert "Traceback" not in error


def test_audio_requires_ffprobe(image_path, tmp_path, monkeypatch, capsys):
    audio = tmp_path / "audio.wav"
    audio.touch()
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/bin/ffmpeg" if name == "ffmpeg" else None)
    assert run_cli(image_path, tmp_path, "--audio", str(audio)) == 1
    assert "ffprobe not found on PATH" in capsys.readouterr().err


def test_missing_input_has_path(tmp_path, capsys):
    missing = tmp_path / "missing.png"
    assert run_cli(missing, tmp_path) == 1
    assert f"input file not found: {missing}" in capsys.readouterr().err


def test_invalid_image_has_actionable_error(image_path, tmp_path, capsys):
    image_path.write_text("not an image")
    assert run_cli(image_path, tmp_path) == 1
    assert "use a valid PNG or JPEG" in capsys.readouterr().err


def test_missing_output_directory(image_path, tmp_path, capsys):
    assert run_cli(image_path, tmp_path / "missing") == 1
    assert "output directory does not exist" in capsys.readouterr().err


def test_invalid_region_plan_names_file(image_path, tmp_path, monkeypatch, capsys):
    plan = tmp_path / "plan.json"
    plan.write_text('{"regions": [}')
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}")
    assert run_cli(image_path, tmp_path, "--regions", str(plan)) == 1
    error = capsys.readouterr().err
    assert f"invalid region plan '{plan}'" in error
    assert "Traceback" not in error


def test_output_cannot_overwrite_audio(image_path, tmp_path, capsys):
    audio = tmp_path / "out.mp4"
    audio.write_bytes(b"keep this input")
    assert run_cli(image_path, tmp_path, "--audio", str(audio)) == 1
    assert "different from every input" in capsys.readouterr().err
    assert audio.read_bytes() == b"keep this input"


@pytest.mark.parametrize("option,value", [
    ("--size", "1080"), ("--size", "0x1920"), ("--size", "1081x1920"),
    ("--size", "1080x1920x30"), ("--size", "1080xnan"),
    ("--fps", "0"), ("--fps", "-1"), ("--fps", "nan"), ("--fps", "29.5"),
])
def test_invalid_output_options_fail_before_render(image_path, tmp_path, option, value):
    with pytest.raises(SystemExit) as error:
        run_cli(image_path, tmp_path, option, value)
    assert error.value.code == 2
    assert not (tmp_path / "out.mp4").exists()


def test_output_options_are_passed_to_renderer(image_path, tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}")

    def render(scenes, output, **kwargs):
        captured.update(kwargs)
        return [scenes[0].duration]

    monkeypatch.setattr(cli, "render_video", render)
    assert run_cli(image_path, tmp_path, "--size", "1080x1920", "--fps", "30") == 0
    assert captured["output_size"] == (1080, 1920)
    assert captured["fps"] == 30
