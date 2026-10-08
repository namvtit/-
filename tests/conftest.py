from pathlib import Path
import subprocess
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def real_clip(tmp_path):
    """A deterministic local media fixture, never an external-service substitute."""
    output = tmp_path / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000", "-t", "2",
        "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", "-c:a", "aac", str(output),
    ], check=True)
    return output
