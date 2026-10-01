# fpSup Base + HDMI + LTC

A fork of [ijigen/fpSup](https://github.com/ijigen/fpSup) for the SIGMA fp (firmware 5.02 only). It is fpSup-Gyro-Base v1.14.0 plus gyro logging when you record to an external HDMI recorder, such as an Atomos Ninja V recording ProRes RAW: one log per take, with that take's focal length and timecode.

Since hdmi5 it also sends the fp's timecode as SMPTE LTC on HDMI audio channel 1, so an audio recorder with an LTC input (tested: Sound Devices MixPre-6) follows the camera's timecode through the recorder's headphone out. See [Timecode to an audio recorder](#timecode-to-an-audio-recorder).

Companion tool: [gyroflow-batch-resolve](https://github.com/unremarkablegarden/gyroflow-batch-resolve) matches every recorder clip to its gyro log and writes a `.gyroflow` file for each, for the Gyroflow plugin in DaVinci Resolve and other editors.

## Install

1. Download this repository (**Code → Download ZIP**) and open [`release/fpSup-Base-HDMI-v1.14.0-hdmi5/`](release/fpSup-Base-HDMI-v1.14.0-hdmi5/).
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

## Timecode to an audio recorder

The fp sends its running timecode as SMPTE LTC on HDMI audio channel 1; channel 2 keeps the fp microphone.

The fp already sends timecode over HDMI as metadata: a maker-specific data packet beside the picture, with the record start/stop flag. HDMI has no standard timecode field, so only a device that knows Sigma's packet reads it; the Ninja does, and the MixPre-6's list of supported cameras has no Sigma. LTC (linear timecode, SMPTE 12M) is the same value encoded as sound: one 80-bit word per frame, biphase-mark coded, which at 24 fps sounds like a 1–2 kHz buzz. As audio it passes through any audio path, including the Ninja's headphone out, and any LTC input can read it. It costs the fp mic one channel. The Ninja also records it on an audio track, and DaVinci Resolve can set a clip's timecode from an LTC audio track in post (not tested here).

Cable it as:

`fp HDMI → Ninja V → Ninja headphone out → recorder LTC input`

- Ninja: monitor the HDMI 1/2 pair on the headphones, volume about 75 %.
- MixPre-6: Advanced mode, Inputs → Aux In Mode = Timecode, Timecode → TC Mode = Aux In.
- fp: 24.00 fps (not 23.98) and Free Run timecode. Other frame rates send wrong LTC.

The recorder follows the fp as long as the cable is in, including after timecode resets and menu use. How it works, what was found in the fp's audio path, and how it was tested: [docs/LTC_HDMI_AUDIO.md](docs/LTC_HDMI_AUDIO.md). When the Ninja also records its analog input, that goes to tracks 1–2 and the HDMI audio (LTC on 3, fp mic on 4) moves to 3–4.


With HDMI RAW out the internal recorder never runs, so upstream's hooks never fire. This fork adds four hooks, built like upstream's and restored when the camera powers off:

| Hook | Site | Does |
|---|---|---|
| `hdmi_start` | `0xC0517D48` in `HdmiRecStart` | opens a log when the recorder connects |
| `hdmi_stop` | `0xC0517D98` in `HdmiRecStop` | closes it when the recorder disconnects or the camera powers off |
| `key_split` | `0xC02DBC0C` in the key-event post | on REC (`0x1E`) or full shutter press (`0x06`): closes the log and opens the next |
| `ltc` | `0xC01FF3A8`, first word of the DspAudioDevice audio callback | writes LTC into channel 1 of the audio monitor ring, which the fp sends out as HDMI audio |

The fp keeps no recording state for an external recorder: REC and the shutter only post key events, and the recorder toggles on them. Splitting on every press needs no state, so a press the recorder ignores costs one extra log and nothing goes out of step.

The lens profile reads the current focal length from `0xC30339A8` and the running timecode from `0xC31CC3F8` (hours, minutes, seconds, frames). HDMI logs are named `H<reel>_<n>` and never overwrite an earlier file.

The `ltc` site gets a `b`, not a `bl`: the callback is a leaf, so `lr` still holds its caller's return address. It patches the callback's code rather than its registered pointer, because the monitor registers the pointer again whenever it restarts (on menu close). The routine is in `gyro/ltc/`: `ltc_core.h` is the encoder, `ltc_cb.c` the callback body, `build_ltc.py` builds it into one position-independent blob that the writer blob carries. The audio ring holds 48 kHz frames of 32 bits, channel 1 in the low half; the routine writes the block two ahead of the DSP's ring position, the first one the HDMI output reads cleanly.

`--edition trace` builds a diagnostic card that records RAM changes and hook calls into the `.GYR`; `gyro/trace_decode.py` prints them.

This fork holds only what builds and tests this card. For the rest of fpSup, go upstream.

## Tested

SIGMA fp 5.02, Atomos Ninja V, ProRes RAW 3840×2160 24p, SIGMA 28-70mm F2.8 DG DN: internal takes log as upstream; takes started with REC and with the shutter each get their own log, with the right focal length and a timecode within one frame of the clip's; Gyroflow syncs them within a few milliseconds.

LTC, SIGMA fp 5.02 with Ninja V and MixPre-6 (Series I) on the Ninja's headphone out: the MixPre locked to the fp's timecode from the hdmi5 card. Loaded over the USB shell beforehand, the same routine stayed frame-matched for 5 minutes and followed timecode resets and menu use. Frame accuracy of the MixPre's file stamp (a clap test) is not measured yet.

## Build

Needs Python 3 and clang (Xcode command line tools on macOS). The LTC emulator test also needs `unicorn` (`pip install unicorn`) and `ltcdump` (`brew install ltc-tools`).

```bash
python3 gyro/build_base_card.py --edition base --version v1.14.0-hdmi5 --four-box-bar --out build/fpSup-Base-HDMI-v1.14.0-hdmi5
cd gyro && python3 test_imu_stream.py && python3 test_lifecycle.py && python3 test_gcsv_format.py
cd ltc && python3 test_ltc_emu.py
```

The build is reproducible: it produces the files in `release/fpSup-Base-HDMI-v1.14.0-hdmi5/` byte for byte (see `SHA256SUMS.txt`). It writes to `build/` so a test build cannot overwrite the release. hdmi4, without LTC, is commit `10c163a`.

## Credits

fpSup is the work of [ijigen](https://github.com/ijigen) and the fpSup contributors ([Discord](https://discord.gg/WVTCcpGUYC)). This fork adds the HDMI logging and is meant to go back upstream.
