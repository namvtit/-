"""Validate real media and conform narration-led upstream output to target duration."""
import asyncio
import json
import math
from pathlib import Path
from apps.api.schemas.video import VideoMetadata


async def run_process(*args: str, timeout: int = 30) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except (asyncio.CancelledError, TimeoutError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        # Tool stderr is for local diagnostics; no provider secrets are passed here.
        raise ValueError(f"{args[0]} failed: {stderr.decode(errors='replace')[-1200:]}")
    return stdout


async def inspect_media(path: Path, require_audio: bool = True) -> VideoMetadata:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("MP4 output is missing or empty.")
    try:
        raw = await run_process("ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path))
        info = json.loads(raw)
        streams = info["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        audio = next((s for s in streams if s["codec_type"] == "audio"), None)
        duration = float(info["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0 or not video["width"] or not video["height"]:
            raise ValueError("Video has invalid dimensions or duration.")
        if require_audio and audio is None:
            raise ValueError("Rendered MP4 has no narration audio stream.")
        return VideoMetadata(duration=duration, width=video["width"], height=video["height"],
                             size_bytes=path.stat().st_size, video_codec=video["codec_name"],
                             audio_codec=audio["codec_name"] if audio else "none")
    except (KeyError, StopIteration, json.JSONDecodeError) as exc:
        raise ValueError("ffprobe could not validate this video.") from exc


def tempo_filter(factor: float) -> str:
    factors = []
    while factor > 2:
        factors.append(2.0)
        factor /= 2
    while factor < 0.5:
        factors.append(0.5)
        factor *= 2
    return ",".join(f"atempo={value:.8f}" for value in [*factors, factor])


async def finalize(source: Path, destination: Path, duration: int, aspect: str) -> VideoMetadata:
    metadata = await inspect_media(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".partial.mp4")
    scale = duration / metadata.duration
    try:
        await run_process(
            "ffmpeg", "-y", "-v", "error", "-i", str(source),
            "-vf", f"setpts={scale:.8f}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=1",
            "-af", f"{tempo_filter(1 / scale)},apad",
            "-t", str(duration), "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "23", "-pix_fmt", "yuv420p", "-threads", "2",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(temp), timeout=900,
        )
        result = await inspect_media(temp)
        expected = 9 / 16 if aspect == "9:16" else 16 / 9
        if abs(result.duration - duration) > 0.2 or abs(result.width / result.height - expected) > 0.01:
            raise ValueError("Rendered video did not meet requested duration or aspect ratio.")
        temp.replace(destination)
        return result
    finally:
        temp.unlink(missing_ok=True)
