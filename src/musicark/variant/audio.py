"""Decoded-audio comparison primitives for v0.5.1 variant detection.

The module deliberately avoids byte/codec hashes. A bundled ffmpeg runtime
normalizes supported input formats to one mono signed-16 PCM stream;
comparison then operates on decoded audio.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from array import array
from collections.abc import Iterable, Sequence
import math
from pathlib import Path
import shutil
import statistics
import subprocess

from .models import AlteredRegion, AudioComparison, DecodedAudio
from .policy import (
    ALIGNMENT_FRAME_SECONDS,
    ALIGNMENT_MIN_CONFIDENCE,
    DECODE_TIMEOUT_SECONDS,
    HOP_SECONDS,
    LOW_SIMILARITY_THRESHOLD,
    MAX_ALIGNMENT_OFFSET_SECONDS,
    MIN_AUDIO_SECONDS,
    SAMPLE_RATE,
    STRONG_DIVERGENCE_THRESHOLD,
    WINDOW_SECONDS,
)


class AudioDecodeError(RuntimeError):
    pass


class AudioDecoderUnavailable(AudioDecodeError):
    pass


class AudioDecoder(ABC):
    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def decode(self, path: Path) -> DecodedAudio: ...


def _resolve_ffmpeg_executable() -> str | None:
    """Prefer MusicArk's packaged ffmpeg binary, then fall back to PATH.

    ``imageio-ffmpeg`` publishes platform wheels containing an ffmpeg binary on
    supported desktop targets. This keeps audio verification self-contained for
    packaged/dev installs and removes the requirement for users to install
    ffmpeg separately.
    """

    try:
        from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore[import-not-found]

        return str(get_ffmpeg_exe())
    except (ImportError, RuntimeError, OSError):
        return shutil.which("ffmpeg")


class FfmpegAudioDecoder(AudioDecoder):
    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable if executable is not None else _resolve_ffmpeg_executable()

    @property
    def available(self) -> bool:
        return bool(self._executable)

    def decode(self, path: Path) -> DecodedAudio:
        if not self._executable:
            raise AudioDecoderUnavailable("Аудиосравнение недоступно: встроенный декодер не найден")
        if not path.is_file():
            raise AudioDecodeError(f"Audio file is missing: {path}")
        command = [
            self._executable,
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map_metadata",
            "-1",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=DECODE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise AudioDecodeError("ffmpeg decode timed out") from exc
        except OSError as exc:
            raise AudioDecodeError(f"ffmpeg could not be started: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace").strip()
            raise AudioDecodeError(f"ffmpeg decode failed: {detail or 'unknown error'}")
        if not completed.stdout:
            raise AudioDecodeError("Decoded audio is empty")
        samples = array("h")
        samples.frombytes(completed.stdout)
        if samples.itemsize != 2:
            raise AudioDecodeError("Unexpected PCM sample width")
        # ffmpeg emits little-endian s16le. Keep the compact array instead of
        # expanding millions of samples into Python int objects.
        import sys

        if sys.byteorder != "little":
            samples.byteswap()
        return DecodedAudio(samples, SAMPLE_RATE)  # type: ignore[arg-type]


class AudioAligner:
    """Coarse bounded alignment using normalized energy-envelope correlation."""

    def align(self, reference: DecodedAudio, local: DecodedAudio) -> tuple[float, float]:
        if reference.sample_rate != local.sample_rate:
            raise ValueError("Audio sample rates must match")
        frame = max(1, int(reference.sample_rate * ALIGNMENT_FRAME_SECONDS))
        ref = _energy_envelope(reference.samples, frame)
        loc = _energy_envelope(local.samples, frame)
        max_shift = int(MAX_ALIGNMENT_OFFSET_SECONDS / ALIGNMENT_FRAME_SECONDS)
        best_shift = 0
        best_score = -1.0
        for shift in range(-max_shift, max_shift + 1):
            pairs = _aligned_pairs(ref, loc, shift)
            if len(pairs) < 8:
                continue
            score = _cosine((a for a, _ in pairs), (b for _, b in pairs))
            if score > best_score:
                best_score = score
                best_shift = shift
        if best_score < 0:
            return 0.0, 0.0
        return best_shift * ALIGNMENT_FRAME_SECONDS, max(0.0, min(1.0, best_score))


class SegmentComparator:
    """Compare aligned decoded PCM in overlapping windows and merge divergences."""

    def compare(
        self,
        reference: DecodedAudio,
        local: DecodedAudio,
        *,
        offset_seconds: float,
        alignment_confidence: float,
    ) -> AudioComparison:
        if reference.sample_rate != local.sample_rate:
            raise ValueError("Audio sample rates must match")
        if min(reference.duration_seconds, local.duration_seconds) < MIN_AUDIO_SECONDS:
            raise ValueError("audio_too_short")
        rate = reference.sample_rate
        shift_samples = int(round(offset_seconds * rate))
        ref_start = max(0, -shift_samples)
        loc_start = max(0, shift_samples)
        overlap = min(len(reference.samples) - ref_start, len(local.samples) - loc_start)
        window = max(1, int(WINDOW_SECONDS * rate))
        hop = max(1, int(HOP_SECONDS * rate))
        if overlap < window:
            raise ValueError("insufficient_aligned_overlap")

        similarities: list[tuple[float, float]] = []
        pos = 0
        while pos + window <= overlap:
            ref_slice = reference.samples[ref_start + pos : ref_start + pos + window]
            loc_slice = local.samples[loc_start + pos : loc_start + pos + window]
            similarity = _window_similarity(ref_slice, loc_slice, rate)
            similarities.append(((ref_start + pos) / rate, similarity))
            pos += hop
        if not similarities:
            raise ValueError("no_comparison_windows")

        values = [value for _, value in similarities]
        low = [item for item in similarities if item[1] < LOW_SIMILARITY_THRESHOLD]
        regions = _merge_regions(similarities)
        return AudioComparison(
            alignment_offset_seconds=offset_seconds,
            alignment_confidence=alignment_confidence,
            global_similarity=sum(values) / len(values),
            median_window_similarity=statistics.median(values),
            low_similarity_window_ratio=len(low) / len(values),
            altered_regions=regions,
            window_count=len(values),
        )


class AudioVerifier:
    def __init__(
        self,
        decoder: AudioDecoder | None = None,
        aligner: AudioAligner | None = None,
        comparator: SegmentComparator | None = None,
    ) -> None:
        self.decoder = decoder or FfmpegAudioDecoder()
        self.aligner = aligner or AudioAligner()
        self.comparator = comparator or SegmentComparator()

    @property
    def available(self) -> bool:
        return self.decoder.available

    def compare(self, reference_path: Path, local_path: Path) -> AudioComparison:
        reference = self.decoder.decode(reference_path)
        local = self.decoder.decode(local_path)
        offset, confidence = self.aligner.align(reference, local)
        if confidence < ALIGNMENT_MIN_CONFIDENCE:
            raise ValueError("alignment_failed")
        return self.comparator.compare(
            reference,
            local,
            offset_seconds=offset,
            alignment_confidence=confidence,
        )


def _energy_envelope(samples: Sequence[int], frame: int) -> list[float]:
    values: list[float] = []
    for start in range(0, len(samples) - frame + 1, frame):
        chunk = samples[start : start + frame]
        mean_square = sum(float(v) * float(v) for v in chunk) / max(1, len(chunk))
        values.append(math.sqrt(mean_square))
    if not values:
        return []
    scale = max(values) or 1.0
    return [value / scale for value in values]


def _aligned_pairs(ref: list[float], loc: list[float], shift: int) -> list[tuple[float, float]]:
    ref_start = max(0, -shift)
    loc_start = max(0, shift)
    count = min(len(ref) - ref_start, len(loc) - loc_start)
    return [(ref[ref_start + i], loc[loc_start + i]) for i in range(max(0, count))]


def _cosine(left: Iterable[float], right: Iterable[float]) -> float:
    a = list(left)
    b = list(right)
    count = min(len(a), len(b))
    if count == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(count))
    na = math.sqrt(sum(a[i] * a[i] for i in range(count)))
    nb = math.sqrt(sum(b[i] * b[i] for i in range(count)))
    if na <= 1e-12 or nb <= 1e-12:
        return 1.0 if na <= 1e-12 and nb <= 1e-12 else 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _bounded_scalar_similarity(left: float, right: float, floor: float) -> float:
    denominator = max(abs(left), abs(right), floor)
    return max(0.0, min(1.0, 1.0 - abs(left - right) / denominator))


def _window_similarity(reference: Sequence[int], local: Sequence[int], sample_rate: int) -> float:
    ref_features = _features(reference, sample_rate)
    local_features = _features(local, sample_rate)
    envelope_similarity = _cosine(ref_features[:16], local_features[:16])
    spectral_similarity = _cosine(ref_features[16:26], local_features[16:26])
    zcr_similarity = _bounded_scalar_similarity(ref_features[-2], local_features[-2], 0.05)
    derivative_similarity = _bounded_scalar_similarity(ref_features[-1], local_features[-1], 0.05)
    # Spectrum gets the strongest weight so a same-loudness replacement tone/noise
    # cannot be hidden by an otherwise similar RMS envelope.
    return max(
        0.0,
        min(
            1.0,
            0.25 * envelope_similarity
            + 0.60 * spectral_similarity
            + 0.075 * zcr_similarity
            + 0.075 * derivative_similarity,
        ),
    )


def _features(samples: Sequence[int], sample_rate: int) -> list[float]:
    if not samples:
        return [0.0] * 28
    # Loudness envelope: robust to codec and uniform gain changes.
    subframes = 16
    block = max(1, len(samples) // subframes)
    envelope: list[float] = []
    for index in range(subframes):
        chunk = samples[index * block : min(len(samples), (index + 1) * block)]
        if not chunk:
            envelope.append(0.0)
            continue
        rms = math.sqrt(sum(float(v) * float(v) for v in chunk) / len(chunk))
        envelope.append(math.log1p(rms))

    # Compact spectral signature. Goertzel avoids a NumPy/ML dependency while
    # remaining insensitive to waveform phase and uniform volume scaling.
    frequencies = (90.0, 140.0, 220.0, 330.0, 500.0, 750.0, 1100.0, 1600.0, 2300.0, 3200.0)
    spectral = [math.log1p(_goertzel_power(samples, sample_rate, frequency)) for frequency in frequencies]

    zero_crossings = 0
    derivative = 0.0
    prev = samples[0]
    for value in samples[1:]:
        if (prev < 0 <= value) or (prev >= 0 > value):
            zero_crossings += 1
        derivative += abs(value - prev)
        prev = value
    zcr = zero_crossings / max(1, len(samples) - 1)
    diff = derivative / max(1.0, (len(samples) - 1) * 32768.0)
    return [*envelope, *spectral, zcr * 10.0, diff * 10.0]


def _goertzel_power(samples: Sequence[int], sample_rate: int, frequency: float) -> float:
    # Decimate only enough to reduce CPU while keeping the requested frequency below Nyquist.
    step = 2 if frequency < sample_rate / 4 else 1
    effective_rate = sample_rate / step
    omega = 2.0 * math.pi * frequency / effective_rate
    coeff = 2.0 * math.cos(omega)
    s_prev = 0.0
    s_prev2 = 0.0
    count = 0
    for index in range(0, len(samples), step):
        sample = samples[index] / 32768.0
        current = sample + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = current
        count += 1
    if count == 0:
        return 0.0
    power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2
    return max(0.0, power / count)


def _merge_regions(similarities: list[tuple[float, float]]) -> tuple[AlteredRegion, ...]:
    regions: list[AlteredRegion] = []
    active: list[tuple[float, float]] = []

    def flush() -> None:
        nonlocal active
        if not active:
            return
        values = [value for _, value in active]
        # Ignore isolated mild outliers; retain a single very strong divergence.
        if len(active) >= 2 or min(values) < STRONG_DIVERGENCE_THRESHOLD:
            start = active[0][0]
            end = active[-1][0] + WINDOW_SECONDS
            regions.append(
                AlteredRegion(
                    start_seconds=start,
                    end_seconds=end,
                    mean_similarity=sum(values) / len(values),
                    minimum_similarity=min(values),
                )
            )
        active = []

    for start, similarity in similarities:
        if similarity < LOW_SIMILARITY_THRESHOLD:
            if active and start - active[-1][0] > HOP_SECONDS * 1.6:
                flush()
            active.append((start, similarity))
        else:
            flush()
    flush()
    return tuple(regions)
