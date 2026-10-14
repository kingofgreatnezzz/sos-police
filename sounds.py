"""
sounds.py
=================================================================================
Sound generator for the Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================================

WHY GENERATE SOUNDS INSTEAD OF DOWNLOADING THEM?
------------------------------------------------
The defence demonstration must not depend on the internet.  Downloading a
ringtone from a CDN would fail on a venue with no Wi-Fi, and shipping binary
audio is awkward.  Instead this module *synthesises* both sounds with nothing
but Python's standard library (``wave``, ``struct``, ``array``, ``math``) the
first time the application runs, and caches them as ordinary WAV files under
``assets/sounds/``.  Every later run simply reuses the files.

Two sounds are produced
-----------------------
sos_beep.wav
    A short, reassuring three-note rising confirmation chime played on the
    CITIZEN's phone the moment the SOS alert has been saved to the database.

sos_alarm.wav
    A loud, continuous duty-desk RINGING ALARM played (on loop) on the POLICE
    COMMAND dashboard when a new ACTIVE SOS alert arrives.  It follows a
    classic telephone ring cadence - ring, ring, pause - so that it is
    unmistakable in a control room.

Both files are 22 050 Hz, 16-bit, mono PCM - a format every browser plays.
"""

from __future__ import annotations

import math
import struct
import wave
from array import array
from pathlib import Path

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
SOUND_DIR: Path = BASE_DIR / "assets" / "sounds"

BEEP_FILE: Path = SOUND_DIR / "sos_beep.wav"
ALARM_FILE: Path = SOUND_DIR / "sos_alarm.wav"

SAMPLE_RATE: int = 22050          # Hz - good quality, small files
MAX_AMPLITUDE: float = 32767.0    # 16-bit signed PCM


# ---------------------------------------------------------------------
# Low level DSP helpers (pure standard library)
# ---------------------------------------------------------------------
def _fade(index: int, total: int, fade_samples: int) -> float:
    """
    Return a 0..1 gain envelope with short fade-in and fade-out ramps.

    Without these ramps a tone that starts or stops abruptly produces an
    audible click (a step discontinuity in the waveform).
    """
    if fade_samples <= 0:
        return 1.0
    if index < fade_samples:
        return index / fade_samples
    remaining = total - index
    if remaining < fade_samples:
        return max(0.0, remaining / fade_samples)
    return 1.0


def _tone(frequency: float, duration: float, amplitude: float,
          fade_ms: float = 8.0, harmonic: float = 0.0) -> list[float]:
    """
    Generate a sine tone.

    Parameters
    ----------
    frequency : float
        Frequency in Hz.
    duration : float
        Length in seconds.
    amplitude : float
        Peak amplitude, 0.0 - 1.0.
    fade_ms : float
        Fade-in / fade-out length in milliseconds (prevents clicks).
    harmonic : float
        Amount of a second harmonic to add (0.0 - 1.0).  A little harmonic
        makes a tone sound louder and more "alarm-like" on small speakers.
    """
    total = int(SAMPLE_RATE * duration)
    fade_samples = int(SAMPLE_RATE * fade_ms / 1000.0)
    samples: list[float] = []
    for index in range(total):
        t = index / SAMPLE_RATE
        value = math.sin(2.0 * math.pi * frequency * t)
        if harmonic:
            value += harmonic * math.sin(4.0 * math.pi * frequency * t)
        value *= _fade(index, total, fade_samples)
        samples.append(value * amplitude)
    return samples


def _warble(duration: float, amplitude: float, centre_hz: float = 1150.0,
            swing_hz: float = 380.0, rate_hz: float = 16.0,
            fade_ms: float = 8.0) -> list[float]:
    """
    Generate a frequency-modulated "warble" - the characteristic sound of a
    telephone ring or a control-room alarm.  The pitch sweeps up and down at
    ``rate_hz`` times per second around ``centre_hz``.
    """
    total = int(SAMPLE_RATE * duration)
    fade_samples = int(SAMPLE_RATE * fade_ms / 1000.0)
    samples: list[float] = []
    phase = 0.0
    for index in range(total):
        t = index / SAMPLE_RATE
        frequency = centre_hz + swing_hz * math.sin(2.0 * math.pi * rate_hz * t)
        # Integrate the frequency to keep the phase continuous.
        phase += 2.0 * math.pi * frequency / SAMPLE_RATE
        value = math.sin(phase) + 0.35 * math.sin(2.0 * phase)
        value *= _fade(index, total, fade_samples)
        samples.append(value * amplitude * 0.75)
    return samples


def _silence(duration: float) -> list[float]:
    """Generate a block of silence."""
    return [0.0] * int(SAMPLE_RATE * duration)


def _mix(*tracks: list[float]) -> list[float]:
    """Mix several equally long sample lists together, clipping safely."""
    length = max(len(track) for track in tracks)
    out: list[float] = []
    for index in range(length):
        total = 0.0
        for track in tracks:
            if index < len(track):
                total += track[index]
        out.append(max(-1.0, min(1.0, total)))
    return out


def _write_wav(path: Path, samples: list[float]) -> Path:
    """Write a list of -1.0..1.0 floats to a 16-bit mono WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    pcm = array("h")
    for value in samples:
        clipped = max(-1.0, min(1.0, value))
        pcm.append(int(clipped * MAX_AMPLITUDE))

    # ``array`` is little-endian on Windows; WAV requires little-endian PCM,
    # so byteswap only if we ever run on a big-endian machine.
    import sys

    if sys.byteorder == "big":  # pragma: no cover - Windows is little-endian
        pcm.byteswap()

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())

    return path


# ---------------------------------------------------------------------
# Sound 1 - the citizen confirmation beep
# ---------------------------------------------------------------------
def generate_beep(path: Path = BEEP_FILE) -> Path:
    """
    Three rising notes - a calm, reassuring "your message was received" chime.

    Cadence: 660 Hz -> 880 Hz -> 1320 Hz, ending on a longer held note.
    """
    samples = (
        _tone(660.0, 0.14, 0.55)
        + _silence(0.04)
        + _tone(880.0, 0.14, 0.55)
        + _silence(0.04)
        + _tone(1320.0, 0.42, 0.60, harmonic=0.18)
    )
    return _write_wav(path, samples)


# ---------------------------------------------------------------------
# Sound 2 - the police control-room ringing alarm
# ---------------------------------------------------------------------
def generate_alarm(path: Path = ALARM_FILE, cycles: int = 3) -> Path:
    """
    A loud telephone-style ringing alarm, roughly 6.3 seconds long.

    One cycle is:

        RING!  0.45 s  ->  gap 0.15 s  ->  RING!  0.45 s  ->  pause 1.05 s

    The clip is played with ``loop=True`` by Streamlit, so the ringing
    continues until the dispatcher acknowledges the alert.  Three cycles give
    a file of about 265 kB, which starts playing instantly.
    """
    samples: list[float] = []
    for _ in range(cycles):
        samples += _warble(0.45, 0.95)
        samples += _silence(0.15)
        samples += _warble(0.45, 0.95)
        samples += _silence(1.05)

    # A short "attention" double blip at the very front of the clip so the
    # alarm is recognisable even if the officer only hears the first moment.
    lead_in = _mix(
        [0.0] * int(SAMPLE_RATE * 0.0),
    )
    samples = lead_in + samples
    return _write_wav(path, samples)


# ---------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------
def ensure_sounds(force: bool = False) -> dict:
    """
    Create both WAV files if they are missing (or if ``force`` is True).

    Returns
    -------
    dict
        ``{"beep": Path, "alarm": Path, "created": [names...]}``

    This function is safe to call on every application run: it checks the
    file system first and only synthesises what is missing.
    """
    created: list[str] = []

    if force or not BEEP_FILE.exists() or BEEP_FILE.stat().st_size < 1000:
        generate_beep(BEEP_FILE)
        created.append(BEEP_FILE.name)

    if force or not ALARM_FILE.exists() or ALARM_FILE.stat().st_size < 1000:
        generate_alarm(ALARM_FILE)
        created.append(ALARM_FILE.name)

    return {"beep": BEEP_FILE, "alarm": ALARM_FILE, "created": created}


def read_sound_bytes(which: str = "alarm") -> bytes:
    """
    Return the raw bytes of a sound file, generating it first if necessary.

    ``which`` is either ``"beep"`` or ``"alarm"``.  Returns ``b""`` if the
    file cannot be produced, so that a sound failure can never break the
    alerting itself.
    """
    try:
        ensure_sounds()
        path = BEEP_FILE if which == "beep" else ALARM_FILE
        if path.exists():
            return path.read_bytes()
    except Exception:  # noqa: BLE001 - sound must never break the application
        pass
    return b""


def sound_info() -> str:
    """Short human-readable description, used on the settings/diagnostic line."""
    try:
        ensure_sounds()
        beep_kb = BEEP_FILE.stat().st_size / 1024.0
        alarm_kb = ALARM_FILE.stat().st_size / 1024.0
        return (
            f"Sound files ready — confirmation chime {beep_kb:.0f} kB, "
            f"ringing alarm {alarm_kb:.0f} kB ({SOUND_DIR})"
        )
    except Exception as exc:  # noqa: BLE001
        return f"Sound files unavailable: {exc}"


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    result = ensure_sounds()
    for name in ("beep", "alarm"):
        path: Path = result[name]
        size_kb = path.stat().st_size / 1024.0
        with wave.open(str(path), "rb") as handle:
            seconds = handle.getnframes() / float(handle.getframerate())
        print(f"{path.name:<16} {size_kb:7.1f} kB   {seconds:5.2f} s   "
              f"{path.relative_to(BASE_DIR)}")
    print("\n" + sound_info())
