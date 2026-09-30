# fpSup Gyro Base + HDMI

A fork of [ijigen/fpSup](https://github.com/ijigen/fpSup) for the SIGMA fp (firmware 5.02 only). It is fpSup-Gyro-Base v1.14.0 with one addition: it also logs the gyro when you record to an external HDMI recorder, such as an Atomos Ninja V recording ProRes RAW.

Upstream Base only logs while the camera records internally. With a Ninja attached and HDMI RAW out, pressing REC on the fp produced no gyro file. With this card it does.

Companion tool: [gyroflow-batch-resolve](https://github.com/unremarkablegarden/gyroflow-batch-resolve) takes the SD card and the recorder SSD, matches every clip to its gyro log and writes the `.gyroflow` files for the Gyroflow plugin in Resolve and other editors.

## Download

[`release/fpSup-Base-HDMI-v1.14.0-hdmi2/`](release/fpSup-Base-HDMI-v1.14.0-hdmi2/)

Copy `AutoRun.txt`, `fpSup.BIN` and the `FPSUPUI` folder to the root of the SD card the camera boots from. Boot with the USB cable unplugged. The fpSup logo appears top left and four boxes fill; all four filled means the card is loaded. The card's `README.txt` has the details.

Like every fpSup card, it changes nothing permanently: the changes live in RAM and are written back when the camera powers off. Remove the files to go back to stock.

## What it writes

| Recording to | Files | Where |
|---|---|---|
| Internal CinemaDNG (as upstream) | `A001_037.GYR` + `A001_037.json` | root of the disk the take went to |
| External recorder over HDMI | `H001_001.GYR` + `H001_001.json` | root of the SD card |

`.GYR` is the raw gyro + accelerometer stream at 2499.466 Hz; `.json` is the camera's Gyroflow lens profile. Convert one take with the [fpSup web converter](https://ijigen.github.io/fpSup/gyro/convert/), or a whole card with [gyroflow-batch-resolve](https://github.com/unremarkablegarden/gyroflow-batch-resolve), which also finds each Ninja clip inside the logs and writes `.gyroflow` files for the Gyroflow plugin in DaVinci Resolve and other editors.

## Shooting with a recorder

- An external log covers the whole HDMI session, not one take. It starts at boot if the Ninja is already attached, otherwise at the first REC press on the fp, and runs until HDMI record output ends or the camera is switched off. Clips recorded meanwhile from either REC button are all in it; gyroflow-batch-resolve finds each clip inside the log.
- The Ninja's REC button does not reach the camera, so it cannot start a log on its own. Boot with the Ninja attached, or press REC on the fp once at the start of a session.
- The `.json` of an external take describes the camera's HDMI monitor mode (3856×2170 @59.94), not the recorded clip. Set its size and frame rate to the clip's before using it; gyroflow-batch-resolve does this. The rolling-shutter readout in it (6.16 ms) is not verified for HDMI RAW.

## What is different from upstream

Upstream starts the logger where the internal movie recorder starts (`0xC03790B8`, right after `XC_AudioRecorder::Start`) and stops it in `cDevt_stop` (`0xC038C484`). With HDMI RAW out, the REC button handler `FUN_c04a6720` calls `HdmiRecStart` (`0xC0517D20`) or `HdmiRecStop` (`0xC0517D58`) instead, and the internal recorder never runs.

This fork adds two hooks, in the same way as the upstream ones:

| Hook | Site | Displaced instruction |
|---|---|---|
| `hdmi_start` | `0xC0517D48` in `HdmiRecStart` | `mov r0, #1`, before `FUN_c0017140(1)` |
| `hdmi_stop` | `0xC0517D98` in `HdmiRecStop` | `mov r0, #0`, before `FUN_c0017140(0)` |

Both run the existing start and stop code unchanged. Both functions push `lr` in their first instruction, so a `bl` at these sites is safe. The two sites are journalled with the other hooks and restored at power-off.

`HdmiRecStart` switches HDMI record output on for a session; while it stays on, further REC presses toggle the recorder with a message and do not call it again. When the camera boots with the recorder attached, that happens before the card has armed its hooks. So after arming, `gsup_boot` reads the output state (`0xC3033A50`, 1 = on) and starts the log itself if it is already on, and `hdmi_start` does nothing while a log is running.

The camera's clip counter does not advance when nothing is recorded internally, so an HDMI take gets its own name: `H<reel>_<n>` instead of `A<reel>_<n>`, opened with the create-only mode `0x402`. If the name exists, `n` goes up by one, up to 50 tries, so no earlier log is overwritten and none collides with an internal clip.

Changed files: `gyro/rec_trigger.S`, `gyro/ring_task.inc.S`, `gyro/writer_core.inc.S`, `gyro/gcsv_task.S`, the hook and routine tables in `gyro/imu_stream_deploy.py`, `gyro/ring_task_deploy.py` and `gyro/release_card.py`, the hook counts in `gyro/test_imu_stream.py`, and the card's README text in `gyro/build_base_card.py`. The release is built with the four-box boot screen (`--four-box-bar`).

Everything else in upstream (the other sups, the research, the site) is left out of this fork: it holds only what builds and tests this card. For the full project, go upstream.

## Tested

SIGMA fp firmware 5.02 with an Atomos Ninja V, ProRes RAW 3840×2160 24p:

- An internal take still logs as upstream.
- REC on the fp with the Ninja attached logs `H001_577`.
- Booted with the Ninja attached: the log starts at boot and holds a clip started on the fp and one started on the Ninja, 9.58 s apart in the log and by the clips' Free Run timecode.
- The HDMI logs sync in Gyroflow with a spread of 2.6–8.8 ms across five sync points, and stabilise correctly.

## Build

Needs Python 3 and clang (Xcode command line tools on macOS).

```bash
python3 gyro/build_base_card.py --edition base --version v1.14.0-hdmi2 --four-box-bar --out release/fpSup-Base-HDMI-v1.14.0-hdmi2
cd gyro && python3 test_imu_stream.py && python3 test_lifecycle.py && python3 test_gcsv_format.py
```

The build is reproducible: the command above produces the files in `release/` byte for byte (see `SHA256SUMS.txt`).

## Credits

All of fpSup is the work of [ijigen](https://github.com/ijigen) and the fpSup contributors ([Discord](https://discord.gg/WVTCcpGUYC)). This fork only adds the HDMI hooks and is meant to go back upstream.
