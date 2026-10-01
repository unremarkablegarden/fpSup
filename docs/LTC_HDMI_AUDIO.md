# Timecode out over HDMI audio (LTC on channel 1)

SIGMA fp, firmware 5.02. The fp sends its own running timecode as SMPTE LTC on HDMI audio channel 1, with no sync box. An external recorder carries it on, and an audio recorder with an LTC input follows the camera. This note covers the fp's audio path, how the routine works, how it was found and tested, and what is still open. Code: `gyro/ltc/`. Card integration: `WANT_LTC` in `gyro/build_base_card.py`, `gyro/writer_core.inc.S` and `gyro/gcsv_task.S`.

Status 2026-10-01: in release `fpSup-Base-HDMI-v1.14.0-hdmi5`. Verified on a camera with an Atomos Ninja V and a Sound Devices MixPre-6 (Series I), both loaded over the USB shell and from the card. Frame accuracy of the recorder's file stamp has not been measured yet.

## Why

The original MixPre-6 has no timecode generator and no timecode output. It reads timecode only while a source is connected: LTC on the tip of its 3.5 mm Aux In, or timecode over its micro-HDMI input. The fp has a generator but no LTC output. Its TC-IN on the mic jack only receives, and while it is on the fp records no sound. The Ninja V has no LTC input or output without the AtomX Sync module. So with HDMI and 3.5 mm cables only, nothing in this kit could send the fp's timecode to the MixPre. The fp could do it if its HDMI audio carried LTC.

## Signal chain

`fp HDMI (ch1 = LTC, ch2 = fp mic) → Ninja V → Ninja headphone out → MixPre-6 Aux In`

- Ninja: monitor the HDMI 1/2 pair on the headphones, volume about 75 %. If the Ninja also records its analog input, that goes to tracks 1–2 and the HDMI audio moves to tracks 3–4.
- MixPre-6: Advanced mode, Inputs → Aux In Mode = Timecode, Timecode → TC Mode = Aux In. On Series I firmware below 9.01, Aux In 1 timecode is hidden.
- fp: 24.00 fps and Free Run timecode.

Before any code, the analog path was proven with a generated LTC file played from a Mac into the fp mic input: it came out of the Ninja's headphone jack and the MixPre locked to it. Generator and decoder: `ltcgen` and `ltcdump` from x42 ltc-tools.

## The fp audio path

Addresses are in the 5.02 MAIN image. "Measured" means read or tested on the camera; "read" means from the disassembly only.

### AUD_INT and its callback table

The audio HAL (Thumb, about `0xC00D3E00–0xC00DB000`) creates a task named `AUD_INT` (entry `0xC00D41A0`) and two IRQs: `0x26` for the capture DMA (status `0x30150080`) and `0x0A` for the audio DSP. The task dispatches events to a table of callback pointers at `0xC31CC808` (read; contents measured):

| Slot | Event | Holds (measured) | Argument |
|---|---|---|---|
| `0xC31CC808` | 2 | 0 | DMA write pointer |
| `0xC31CC80C` | 1, capture DMA block | 0 outside internal recording | DMA write pointer, `(*0x301500C4 << 2) + 0x40000000` |
| `0xC31CC810` | 3, DSP block, when mode `*0xC31CC82C == 3` | `0xC01FF3A8` | DSP ring position from `0xC00D80A0` |
| `0xC31CC81C` | every 5th event 3 | `0xC01FF2B0` (level meters) | L, R peak |

### Two devices

- `AsicAudioDevice` (vtable `0xC07E4714`) records to the card. It allocates a `0x2F000` byte ring (48 kHz, 2 ch, 16 bit) and the DMA interrupts every `0x1000` bytes (read).
- `DspAudioDevice` (vtable `0xC07E44AC`, object `0xC31F83F8`) is the live monitor. It allocates two `0x4000` byte buffers (pointers at `0xC31F8410` and `0xC31F8418`) and registers `0xC01FF3A8` as its event-3 callback (measured). The stock callback is a three-word leaf: `mov ip, r0; nop; bx lr`.

The monitor's start routine (`0xC01FF3B8`) returns early when HDMI is connected and HDMI record output is on (`0xC3033A50 == 1`). Even so, the monitor was running with the Ninja connected in RAW output, both when the Ninja came on after the fp and after a cold boot with the Ninja already on (measured).

### The monitor ring feeds HDMI audio

The DSP writes the first monitor buffer as a ring; its bounds are at `0xC31D23EC` (start) and `0xC31D23F0` (end): `0x52B00580..0x52B04580`, `0x4000` bytes (measured). The second buffer stayed all zeros.

- Frames are 32 bits: channel 1 in the low halfword, channel 2 in the high halfword, 16 bit signed (measured: an LTC signal on the fp mic's left input appeared in the low halfword only).
- Event 3 fires 48 times a second, and its argument steps `0x1000` bytes (1024 stereo frames, 21.3 ms) through the ring (measured).
- Writing samples into this ring from the event-3 callback changes what the Ninja receives over HDMI (measured with a 1 kHz square wave).

The DSP microcode is embedded in MAIN (`pcmenc_v477`, `v488`, `v503`, `pcmdec_v474`; read). The HDMI transmitter's audio registers at `0x302A0000` hold configuration only, with no sample FIFO (read). So the DSP or its DMA carries the samples from this ring to HDMI. An earlier devkit note judged HDMI audio injection infeasible because the recording ring holds about a second of audio. The monitor ring is a different buffer, and it is the one HDMI is fed from.

### Which block to write

Event 3's argument is a position in the ring, but nothing said which block the HDMI side reads next. A test routine wrote one block at `r0 + K × 0x1000` (wrapped), with a phase-continuous 1 kHz tone, while K was changed from the host:

| K | Ninja headphones |
|---|---|
| 0 | silent |
| 1 | tone with dropouts |
| 2 | clean |
| 3 | clean |

K = 2 is used: it has a clean block on one side and the partly failing one on the other. A tone that restarts its phase every block buzzes at every K, so the test only works with a continuous phase.

### Monitor restarts re-register the callback

Opening and closing the fp menu, for example to reset the timecode, restarts the monitor. The restart writes `0xC01FF3A8` back into `0xC31CC810` (measured). A hook that swaps the pointer is undone every time. Patching the first word of the stock callback (`0xC01FF3A8`, stock `0xE1A0C000`) instead survives restarts, because the re-registered pointer still lands on the patched code (measured).

The patch is a `b`, not a `bl`. The callback is a leaf and `lr` still holds AUD_INT's return address, so the LTC routine returns straight to AUD_INT. A `bl` there would overwrite `lr`, and the stock `bx lr` would then loop.

### Timecode

- Live timecode: 4 bytes at `0xC31CC3F8`, binary (not BCD): hours, minutes, seconds, frames (measured). The singleton is returned by `0xC00D0498`, and `+0x10` holds a frame-rate enum (read; mapping not worked out).
- It is updated once per video frame by `0xC00CEC10`, registered with the driver behind IRQ `0x61` (read).
- TC-IN: the LTC decoder runs inside the audio DSP. The CPU reads only the decoded words at `0xC31CC834/838`, which AUD_INT refreshes from DSP registers `0x2AA01200/1204` (read). So the TC-IN path offers no CPU-side access to the mic samples.

## The routine

`gyro/ltc/`:

| File | What |
|---|---|
| `ltc_core.h` | The encoder, shared by the camera build and the host test |
| `ltc_cb.c` | The event-3 body: checks the ring bounds, finds block +2, fills its ch1 |
| `ltc_entry.S` | Entry and the 0x40-byte state block; finds the state pc-relatively |
| `build_ltc.py` | Builds one position-independent blob, with the state's initial values written in |
| `test_ltc.c`, `test_ltc_emu.py` | The host test and the unicorn test, see below |

Encoder:

- 48 kHz output. At 24 fps that is 2000 samples per frame and 25 per bit. The build writes fps and samples per bit into the state block, so the camera code does no division.
- Biphase mark: a transition at the start of every bit, plus one half way through a 1. Amplitude ±`0x2000` (−12 dBFS), square edges. The MixPre-6 locks to this through the Ninja's headphone amplifier.
- 80-bit word in the 24/30 fps layout: frames 0–3 and 8–9, seconds 16–19 and 24–26, minutes 32–35 and 40–42, hours 48–51 and 56–57, sync word `0xBFFC` in bits 64–79. The polarity bit 27 is set so that the count of ones is even. User bits are zero.
- The live timecode is read at each LTC frame start. Audio and video frames run at the same nominal rate but an arbitrary phase, so near a video frame boundary the read can land on either side of the change. A value equal to the frame last sent, or to the next one, continues the count; anything else resyncs to the live value. With stopped timecode (Rec Run, not recording) the output alternates between two values, so the routine assumes Free Run.
- State (offsets in `struct ltc`): `+04` enable, `+0C` amplitude, `+10` block offset K, `+34` fps, `+38` samples per bit, `+3C` frames added to the live timecode (to compensate latency, once measured).

The C is compiled freestanding (`-O2 -ffreestanding -fno-builtin -fno-jump-tables -fno-pic -fno-unwind-tables`) to assembly, appended to `ltc_entry.S` and assembled as one `.text` section. `build_ltc.py` rejects the build if the C output contains data, rodata, another section, or a call out.

### On the card

- `WANT_LTC` (Base and trace editions): `gcsv_task.S` includes the blob with `.incbin` as routine `ltc`, slot `+0x4C` of `gsup_offsets`.
- `gsup_boot` arms it with `s_hook_b`. Like `s_hook`, it takes an 8-byte veneer (`ldr pc, [pc, #-4]` and the address) from the cave bump allocator, then writes `b <veneer>` to `0xC01FF3A8` instead of `bl`. The pool is too far from the site for a direct `b` (±32 MB); the cave is not.
- `hook_sites()` declares the site with its stock word, so stage2 journals it and the loader writes it back at power-off.
- The USB deploy builds without `WANT_LTC`; its `ltc` slot stays zero and `s_hook_b` arms nothing.

## How it was found and tested

All of it ran over the fpSup USB shell (`fp_usb_shell/`, `fpshd` and `fpsh mem get/set`), with no card change until the end.

1. Read-only: the HDMI-connected flag, the record-output flag and the device objects, with and without the Ninja. This showed the monitor buffers live.
2. Signal check: with LTC played into the fp mic, the low halfwords of the ring held it and the high halfwords held noise.
3. Probe: an observe-only routine replaced the event-3 pointer. It counted calls and kept the last eight arguments: 48 calls a second, stepping `0x1000`.
4. Injection: a square wave into three blocks after `r0` reached the Ninja. The single-block, continuous-phase version then found K = 2.
5. The encoder was written in C and tested on the host first: `test_ltc.c` writes a 48 kHz WAV, and `ltcdump -f 24` decodes 60 s from 01:00:00:00 with no discontinuity. The simulated video changes at three different phases, including on the LTC frame boundary.
6. `test_ltc_emu.py` runs the camera build under unicorn: it maps the state, ring and timecode addresses, calls the entry once per 1024-sample block with `r0` stepping as on the camera, and requires the output to be identical to the host build and to decode cleanly. It was also run with the blob at a second address, to check position independence. Collecting the wrong block makes the test fail.
7. On the camera, loaded over USB: the MixPre locked and stayed frame-matched to the fp display for 5 minutes. The camera's `sending` and `live` values differed by one or two frames, as expected from two USB reads about 40–80 ms apart. Opening the menu broke it, which led to the code patch, which then survived menu use and timecode resets.
8. The Base card with `WANT_LTC` booted and the MixPre locked. Its `AutoRun.txt` and `fpSup.BIN` are the ones released as hdmi5.

Runtime `mem set` on a firmware code word took effect with no cache maintenance in step 7. Do not rely on that in general: the card publishes its writes with `0xC000E91C` and `0xC000EABC`.

## Limits and open work

- 24.00 fps only. 25 fps needs the polarity bit at 59, not 27, and different flag positions. 23.976 cannot be made from a 48 kHz clock at a whole number of samples per frame.
- Latency: a block is generated about two blocks (42 ms, about one frame) before it is played, plus the Ninja headphone path. The recorder's file stamp may trail the video by about a frame. A clap test is needed to set `offset`.
- Only channel 1 of a two-channel HDMI stream. More channels would mean changing the HDMI transmitter's channel count (`0x302A1034`) and the DSP's output, not attempted.
- Not checked: internal recording with the patch in place. The recording ring (`AsicAudioDevice`) is a different buffer, so it should be unaffected.
- Not tested: the frame-rate enum at `0xC31CC3F8 + 0x10`, which could select the LTC rate automatically.
- Record trigger: the MixPre-6 can start on running LTC (Rec Trigger = Timecode). Sending LTC only while the fp records to the recorder would make the MixPre follow REC, but the fp's HDMI record flag has not been located.
