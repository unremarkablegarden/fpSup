# fpSup Gyro Base + HDMI

A fork of [ijigen/fpSup](https://github.com/ijigen/fpSup) for the SIGMA fp (firmware 5.02 only). It is fpSup-Gyro-Base v1.14.0 plus gyro logging when you record to an external HDMI recorder, such as an Atomos Ninja V recording ProRes RAW: one log per take, with that take's focal length and timecode.

Companion tool: [gyroflow-batch-resolve](https://github.com/unremarkablegarden/gyroflow-batch-resolve) matches every recorder clip to its gyro log and writes a `.gyroflow` file for each, for the Gyroflow plugin in DaVinci Resolve and other editors.

## Install

1. Download this repository (**Code → Download ZIP**) and open [`release/fpSup-Base-HDMI-v1.14.0-hdmi4/`](release/fpSup-Base-HDMI-v1.14.0-hdmi4/).
2. Copy `AutoRun.txt`, `fpSup.BIN`, `FPSUPUI` and `gyro_data` to the root of the SD card the camera boots from.
3. Boot with the USB cable unplugged. The fpSup logo appears top left and four boxes fill when the card is loaded.

Nothing is changed permanently: remove the files to go back to stock.

## What it writes

| Recording to | Files | Where |
|---|---|---|
| Internal CinemaDNG | `A001_037.GYR` + `A001_037.json` | `gyro_data` on the disk the take went to |
| External recorder over HDMI | `H001_001.GYR` + `H001_001.json` | `gyro_data` on the SD card |

`.GYR` is the gyro and accelerometer stream; `.json` is the Gyroflow lens profile, with the focal length and the camera's timecode when the log started.

The camera does not create `gyro_data`. It comes with the card files; on a USB SSD you record to, make one yourself. Without it, logs go to the root of the disk.

## Shooting with a recorder

- Set timecode to **Free Run**, so gyroflow-batch-resolve can place each clip in its log by timecode.
- Start and stop takes with REC or the shutter button on the fp. Each press starts a new log, so every take gets its own log and lens profile; the short logs between takes hold no clip.
- REC on the recorder's own screen does not reach the camera. Such a take has no log of its own, but gyroflow-batch-resolve still finds it inside the log that was running.

Limits:

- The focal length is the one at the start of the take; zooming during a take is not followed, and the distortion coefficients stay the lens's calibration values.
- A log can end a couple of frames before its clip.
- A log opened before the recorder is ready holds no clip and describes the HDMI monitor mode (3856×2170 @59.94). gyroflow-batch-resolve takes size and frame rate from the clip anyway.

## How it works

With HDMI RAW out the internal recorder never runs, so upstream's hooks never fire. This fork adds three hooks, built like upstream's and restored when the camera powers off:

| Hook | Site | Does |
|---|---|---|
| `hdmi_start` | `0xC0517D48` in `HdmiRecStart` | opens a log when the recorder connects |
| `hdmi_stop` | `0xC0517D98` in `HdmiRecStop` | closes it when the recorder disconnects or the camera powers off |
| `key_split` | `0xC02DBC0C` in the key-event post | on REC (`0x1E`) or full shutter press (`0x06`): closes the log and opens the next |

The fp keeps no recording state for an external recorder: REC and the shutter only post key events, and the recorder toggles on them. Splitting on every press needs no state, so a press the recorder ignores costs one extra log and nothing goes out of step.

The lens profile reads the current focal length from `0xC30339A8` and the running timecode from `0xC31CC3F8` (hours, minutes, seconds, frames). HDMI logs are named `H<reel>_<n>` and never overwrite an earlier file.

`--edition trace` builds a diagnostic card that records RAM changes and hook calls into the `.GYR`; `gyro/trace_decode.py` prints them.

This fork holds only what builds and tests this card. For the rest of fpSup, go upstream.

## Tested

SIGMA fp 5.02, Atomos Ninja V, ProRes RAW 3840×2160 24p, SIGMA 28-70mm F2.8 DG DN: internal takes log as upstream; takes started with REC and with the shutter each get their own log, with the right focal length and a timecode within one frame of the clip's; Gyroflow syncs them within a few milliseconds.

## Build

Needs Python 3 and clang (Xcode command line tools on macOS).

```bash
python3 gyro/build_base_card.py --edition base --version v1.14.0-hdmi4 --four-box-bar --out release/fpSup-Base-HDMI-v1.14.0-hdmi4
cd gyro && python3 test_imu_stream.py && python3 test_lifecycle.py && python3 test_gcsv_format.py
```

The build is reproducible: it produces the files in `release/` byte for byte (see `SHA256SUMS.txt`).

## Credits

fpSup is the work of [ijigen](https://github.com/ijigen) and the fpSup contributors ([Discord](https://discord.gg/WVTCcpGUYC)). This fork adds the HDMI logging and is meant to go back upstream.
