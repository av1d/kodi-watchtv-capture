"""Watch TV - Kodi script add-on.

Captures live video and audio from a V4L2 capture device (via ALSA) with
FFmpeg, encodes it to H.264/AAC in an MPEG-TS stream, and sends it to a local
UDP port. Kodi plays that stream. When playback stops or fails, or when Kodi
exits, the FFmpeg capture process is shut down.

Requirements:
    - Linux with FFmpeg installed and available in Kodi's PATH
    - A V4L2 capture device (default: /dev/video0)
    - An ALSA audio capture device (default: hw:CARD=MS210x,DEV=0)
"""

import shutil
import subprocess
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs


# Local UDP address FFmpeg writes to and Kodi reads from.
STREAM = "udp://127.0.0.1:5000"

# FFmpeg's stderr goes here so failures can be diagnosed after the fact.
LOG = xbmcvfs.translatePath("special://temp/watchtv-ffmpeg.log")


class TVPlayer(xbmc.Player):
    """Kodi player that reports playback state through threading events."""

    def __init__(self):
        super().__init__()
        # Set when Kodi has begun decoding audio/video from the stream.
        self.started = threading.Event()
        # Set when playback stops, ends, or fails for any reason.
        self.finished = threading.Event()

    def onAVStarted(self):
        """Called by Kodi once audio and video are playing."""
        self.started.set()

    def onPlayBackStopped(self):
        """Called when the user stops playback."""
        self.finished.set()

    def onPlayBackEnded(self):
        """Called when the stream ends on its own."""
        self.finished.set()

    def onPlayBackError(self):
        """Called when Kodi can't play the stream."""
        self.finished.set()


def main():
    """Start the capture, play it in Kodi, and clean up when done."""
    # Locate FFmpeg before doing anything else, and tell the user if it's missing.
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        xbmcgui.Dialog().ok(
            "Watch TV",
            "FFmpeg wasn't found in Kodi's PATH."
        )
        return

    # FFmpeg command line: capture -> filter -> encode -> UDP stream.
    command = [
        # -nostdin: never wait for keyboard input; warnings only in the log.
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "warning",

        # Video input: V4L2 capture device delivering MJPEG at 720x480.
        # A larger queue prevents dropped frames if the encoder falls behind.
        "-f", "video4linux2",
        "-thread_queue_size", "512",
        "-input_format", "mjpeg",
        "-s", "720x480",
        "-i", "/dev/video0",

        # Audio input: ALSA capture device (the capture card's audio output).
        "-f", "alsa",
        "-thread_queue_size", "1024",
        "-i", "hw:CARD=MS210x,DEV=0",

        # Use video from the first input and audio from the second.
        "-map", "0:v",
        "-map", "1:a",

        # Audio filters: denoise, then boost volume (capture audio is quiet).
        "-af", "afftdn=nr=10,volume=100.0",

        # Video filter: scale down to 680x390.
        "-vf", "scale=680:390",

        # Video encoding: H.264 tuned for the lowest possible latency.
        # yuv420p keeps the output compatible with Kodi's decoders.
        # A keyframe every 30 frames lets playback start and recover quickly.
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-g", "30",

        # Audio encoding: AAC.
        "-c:a", "aac",

        # Output: MPEG-TS over UDP. pkt_size=1316 fits seven 188-byte TS
        # packets in one datagram, which avoids IP fragmentation.
        "-f", "mpegts",
        STREAM + "?pkt_size=1316",
    ]

    monitor = xbmc.Monitor()  # Lets us react when Kodi is shutting down.
    player = TVPlayer()
    process = None
    playback_requested = False  # True once we've asked Kodi to play the stream.

    try:
        # Open the log file for FFmpeg's stderr; it stays open while FFmpeg runs.
        with open(LOG, "w") as logfile:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=logfile,
            )

            # Catch immediate capture-device or encoder errors.
            # waitForAbort returns True if Kodi is exiting.
            if monitor.waitForAbort(1):
                return

            # If FFmpeg has already exited, the capture failed to start.
            if process.poll() is not None:
                raise RuntimeError("FFmpeg couldn't start capture.")

            playback_requested = True
            player.play(STREAM)

            # Allow time for Kodi to recognize the incoming stream.
            # Give up after 30 seconds.
            deadline = time.monotonic() + 30
            while not player.started.is_set():
                if monitor.waitForAbort(0.1):
                    return  # Kodi is shutting down.
                if process.poll() is not None:
                    raise RuntimeError("FFmpeg exited during startup.")
                if player.finished.is_set():
                    return  # User stopped playback or Kodi hit an error.
                if time.monotonic() > deadline:
                    raise RuntimeError("Kodi couldn't open the TV stream.")

            # Playback is running. Keep the script alive until it ends,
            # watching for Kodi shutdown or an FFmpeg crash.
            while not player.finished.is_set():
                if monitor.waitForAbort(0.2):
                    break
                if process.poll() is not None:
                    raise RuntimeError("FFmpeg stopped unexpectedly.")

    except Exception as error:
        # Write the error to kodi.log and show it to the user,
        # along with the location of the FFmpeg log.
        xbmc.log("Watch TV: " + str(error), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            "Watch TV",
            "{}\n\nFFmpeg log:\n{}".format(error, LOG)
        )

    finally:
        # Cleanup runs on every exit path (normal, error, or early return).

        # Stop Kodi's player if we started it and it's still running.
        if playback_requested and not player.finished.is_set():
            player.stop()

        # Stop FFmpeg so the capture device isn't left busy. Ask politely
        # first, then force-kill if it hasn't exited after 3 seconds.
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


# Kodi runs default.py directly as a script, so start immediately.
main()

