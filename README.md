# kodi-watchtv-capture

> **Example add-on: edit it for your own setup.** The video device, audio device, resolution, and port in `default.py` are examples from my hardware. Change them to match your device and settings before you use it.

Watch live video from a Linux capture card in Kodi. This script add-on streams a V4L2/ALSA device through FFmpeg and stops the capture when playback ends.

## How it works

Watch TV starts FFmpeg, which captures video and audio from your capture device and encodes it to H.264/AAC. FFmpeg sends the result as MPEG-TS over local UDP (`udp://127.0.0.1:5000`), and Kodi plays that stream. When playback stops, fails, or Kodi exits, FFmpeg is shut down.

## Requirements

- Linux
- Kodi 19 or later (Python 3)
- FFmpeg in Kodi's PATH
- A V4L2 video device
- An ALSA audio device

## Install

1. Copy the `script.watchtv` folder to `~/.kodi/addons/`.
2. Edit `default.py` for your hardware (see Configure).
3. Restart Kodi.
4. Enable the add-on under **Settings > Add-ons > My add-ons** if it's disabled.
5. Open it from **Add-ons > Program add-ons**.

## Configure

These values in `default.py` are examples and must be changed:

- `/dev/video0` is the video device.
- `hw:CARD=MS210x,DEV=0` is the audio device.
- `720x480` is the capture resolution and `scale=680:390` is the output size.
- `STREAM` is the UDP address and port.

To list your devices, run:

```bash
v4l2-ctl --list-devices
arecord -L
```

## Troubleshooting

- **FFmpeg not found:** install it and make sure Kodi can see it in its PATH.
- **Capture fails to start:** check the FFmpeg log at `~/.kodi/temp/watchtv-ffmpeg.log`.
- **Other errors:** check `~/.kodi/temp/kodi.log` for lines starting with `Watch TV:`.

## License

MIT
