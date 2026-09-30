# fpSup Gyro Base + HDMI

A fork of [ijigen/fpSup](https://github.com/ijigen/fpSup) for the SIGMA fp (firmware 5.02 only). It is fpSup-Gyro-Base v1.14.0 with one addition: it also logs the gyro when you record to an external HDMI recorder, such as an Atomos Ninja V recording ProRes RAW, one log per take with that take's focal length.

Upstream Base only logs while the camera records internally. With a Ninja attached and HDMI RAW out, pressing REC on the fp produced no gyro file. With this card it does.

Companion tool: [gyroflow-batch-resolve](https://github.com/unremarkablegarden/gyroflow-batch-resolve) takes the SD card and the recorder SSD, matches every clip to its gyro log and writes the `.gyroflow` files for the Gyroflow plugin in Resolve and other editors.

## Download

[`release/fpSup-Base-HDMI-v1.14.0-hdmi3/`](release/fpSup-Base-HDMI-v1.14.0-hdmi3/)

Copy `AutoRun.txt`, `fpSup.BIN` and the `FPSUPUI` folder to the root of the SD card the camera boots from. Boot with the USB cable unplugged. The fpSup logo appears top left and four boxes fill; all four filled means the card is loaded. The card's `README.txt` has the details.

Like every fpSup card, it changes nothing permanently: the changes live in RAM and are written back when the camera powers off. Remove the files to go back to stock.

## What it writes

| Recording to | Files | Where |
|---|---|---|
| Internal CinemaDNG (as upstream) | `A001_037.GYR` + `A001_037.json` | root of the disk the take went to |
| External recorder over HDMI | `H001_001.GYR` + `H001_001.json` | root of the SD card |

`.GYR` is the raw gyro + accelerometer stream at 2499.466 Hz; `.json` is the camera's Gyroflow lens profile. Convert one take with the [fpSup web converter](https://ijigen.github.io/fpSup/gyro/convert/), or a whole card with [gyroflow-batch-resolve](https://github.com/unremarkablegarden/gyroflow-batch-resolve), which also finds each Ninja clip inside the logs and writes `.gyroflow` files for the Gyroflow plugin in DaVinci Resolve and other editors.

## Shooting with a recorder

- Start and stop takes with REC or the shutter button on the fp. With HDMI record output on, every REC press and every full shutter press closes the open log and opens the next, so each take gets its own `H…GYR` and `.json`. The logs between takes hold no clip.
- The first log starts when the recorder connects (or at boot, if it is attached); the last ends when the camera is switched off.
- The Ninja's REC button does not reach the camera. A take started there has no log of its own and lies inside whichever log is open; gyroflow-batch-resolve can still find it there.
- The `.json` carries the focal length the camera shows when the log opens, so each take has its own zoom position. Zooming during a take is not followed, and the distortion coefficients are the lens's calibration ones at every zoom position.
- The log opened at connect may still describe the HDMI monitor mode (3856×2170 @59.94); take logs carry the recording mode (e.g. 3840×2160 @24). gyroflow-batch-resolve sets size and frame rate from the clip either way. The rolling-shutter readout (6.16 ms) is not verified for HDMI RAW.
- A take log is up to about 80 ms (2 frames at 24p) shorter than its clip.

## What is different from upstream

Upstream starts the logger where the internal movie recorder starts (`0xC03790B8`, right after `XC_AudioRecorder::Start`) and stops it in `cDevt_stop` (`0xC038C484`). With HDMI RAW out the internal recorder never runs. What does run is `HdmiRecStart` (`0xC0517D20`, called from the HDMI connect handler `FUN_c04a6720`) and `HdmiRecStop` (`0xC0517D58`).

This fork adds two hooks, in the same way as the upstream ones:

| Hook | Site | Displaced instruction |
|---|---|---|
| `hdmi_start` | `0xC0517D48` in `HdmiRecStart` | `mov r0, #1`, before `FUN_c0017140(1)` |
| `hdmi_stop` | `0xC0517D98` in `HdmiRecStop` | `mov r0, #0`, before `FUN_c0017140(0)` |

Both run the existing start and stop code unchanged. Both functions push `lr` in their first instruction, so a `bl` at these sites is safe. The two sites are journalled with the other hooks and restored at power-off.

`HdmiRecStart` and `HdmiRecStop` run when the HDMI record connection starts and ends (recorder plugged in, boot with it attached, unplugged, power-off), not per take. When the camera boots with the recorder attached, `HdmiRecStart` runs before the card has armed its hooks, so after arming `gsup_boot` reads the output state (`0xC3033A50`, 1 = on) and starts the log itself; `hdmi_start` does nothing while a log is running.

The fp does not track a recording state for the external recorder: there is no tally, and a RAM trace of the state, HDMI and recorder objects shows no change on REC. REC and the shutter only post key events, and the Ninja toggles on them. So a third hook splits the log on the key itself:

| Hook | Site | Displaced instruction |
|---|---|---|
| `key_split` | `0xC02DBC0C` in `FUN_c02dbbe8` (key post) | `nop`, after the queue send |

On key `0x1E` (REC down) or `0x06` (shutter full press) with HDMI record output on, it runs the `hdmi_stop` and `hdmi_start` bodies: close the open log, open the next. Both are synchronous. There is no toggle state, so a press the recorder ignores costs one extra split and nothing goes out of step.

The lens profile's focal length came from the lens singleton and the calibration block, which on a zoom hold one value (28.9 on the 28-70 at every position). The current focal length is at `0xC30339A8` (`captureState+0x15C`, tenths of a mm), the value the camera displays. When it differs from the mount's, the profile uses it; otherwise the calibration correction applies as before (`gyro/gcsv_json.S`).

The camera's clip counter does not advance when nothing is recorded internally, so an HDMI take gets its own name: `H<reel>_<n>` instead of `A<reel>_<n>`, opened with the create-only mode `0x402`. If the name exists, `n` goes up by one, up to 50 tries, so no earlier log is overwritten and none collides with an internal clip.

Changed files: `gyro/rec_trigger.S`, `gyro/key_split.S`, `gyro/gcsv_json.S`, `gyro/ring_task.inc.S`, `gyro/writer_core.inc.S`, `gyro/gcsv_task.S`, the hook and routine tables in `gyro/imu_stream_deploy.py`, `gyro/ring_task_deploy.py` and `gyro/release_card.py`, the hook counts in `gyro/test_imu_stream.py`, and the card's README text in `gyro/build_base_card.py`. The release is built with the four-box boot screen (`--four-box-bar`).

Diagnostics: `--edition trace` builds Base plus a RAM diff and marker hooks that write extra records into the `.GYR` (`gyro/trace_diff.S`); `gyro/trace_decode.py` prints them. That is how the key events and the focal-length word were found. It is not a release edition.

Everything else in upstream (the other sups, the research, the site) is left out of this fork: it holds only what builds and tests this card. For the full project, go upstream.

## Tested

SIGMA fp firmware 5.02 with an Atomos Ninja V, ProRes RAW 3840×2160 24p, SIGMA 28-70mm F2.8 DG DN:

- An internal take still logs as upstream.
- Takes started and stopped with fp REC and with the shutter each got their own log: 4.79 / 5.96 / 6.07 / 7.95 s against clips of 4.87 / 6.00 / 6.12 / 7.96 s, with idle logs between them.
- The four take profiles had focal lengths 28.9 / 50.9 / 70.0 / 51.2 for takes shot at 28 / 50 / 70 / 50 mm.
- Earlier session logs (release hdmi2) synced in Gyroflow with a spread of 2.6–8.8 ms across five sync points, and stabilised correctly.

These tests ran on the trace build, which carries the same split and profile code; the release card itself needs one confirmation run.

## Build

Needs Python 3 and clang (Xcode command line tools on macOS).

```bash
python3 gyro/build_base_card.py --edition base --version v1.14.0-hdmi3 --four-box-bar --out release/fpSup-Base-HDMI-v1.14.0-hdmi3
cd gyro && python3 test_imu_stream.py && python3 test_lifecycle.py && python3 test_gcsv_format.py
```

The build is reproducible: the command above produces the files in `release/` byte for byte (see `SHA256SUMS.txt`).

## Credits

All of fpSup is the work of [ijigen](https://github.com/ijigen) and the fpSup contributors ([Discord](https://discord.gg/WVTCcpGUYC)). This fork only adds the HDMI hooks, the per-take split and the live focal length, and is meant to go back upstream.
