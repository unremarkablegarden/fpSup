fpGyroSup Base + HDMI v1.14.0-hdmi1 -- SIGMA fp firmware Ver.5.02 only

INSTALL
    Copy AutoRun.txt, fpSup.BIN and the FPSUPUI folder to the root of the SD
    card the camera boots from.  Boot with the USB cable unplugged: the fpSup
    logo appears top left and four boxes fill; all four filled means loaded.

RECORD
    Internal CinemaDNG     \A001_037.GYR + \A001_037.json
                           in the root of the disk the take went to
    External recorder      \H001_001.GYR + \H001_001.json
    (HDMI RAW, e.g. Ninja) in the root of the SD card

    For external takes, start AND stop with the REC button on the fp body.
    A stop pressed on the recorder does not reach the camera, so the log
    keeps running until the next REC press on the fp.  H numbers count up
    and never overwrite an earlier file.

    The .json of an external take describes the camera's HDMI monitor mode
    (3856x2170 @59.94), not the recorded clip; set its size and frame rate
    to the clip's before use.  gyroflow-batch-resolve does this for you.

CONVERT
    https://ijigen.github.io/fpSup/gyro/convert/     one take, in a browser
    https://github.com/unremarkablegarden/gyroflow-batch-resolve
                                                     a whole card: matches
                                                     takes to recorder clips
                                                     and writes .gyroflow files

REMOVE
    Delete the files or take the card out, then switch the camera off: the
    card writes back every firmware word it changed as the camera powers off.
    If the camera froze, take the battery out (USB cable unplugged).
