fpGyroSup Base + HDMI v1.14.0-hdmi4 -- SIGMA fp firmware Ver.5.02 only

INSTALL
    Copy AutoRun.txt, fpSup.BIN and the FPSUPUI and gyro_data folders to the
    root of the SD card the camera boots from.  Boot with the USB cable
    unplugged: the fpSup logo appears top left and four boxes fill; all four
    filled means loaded.

FOLDER
    Logs go into gyro_data.  The camera does not create it: copy it with the
    card files, and make one in the root of any USB SSD you record to.  On a
    disk without it, logs go to the root.

RECORD
    Internal CinemaDNG     \gyro_data\A001_037.GYR + .json
                           on the disk the take went to
    External recorder      \gyro_data\H001_001.GYR + .json
    (HDMI RAW, e.g. Ninja) on the SD card

    With HDMI record output on, every REC press and every full shutter
    press on the fp closes the open log and opens the next.  Each take gets
    its own log and its own .json; the logs between takes hold no clip.
    The first log starts when the recorder connects (or at boot, if it is
    attached), the last ends when the camera is switched off.  REC on the
    recorder itself does not reach the camera: a take started there has no
    log of its own and lies inside whichever log is open.
    H numbers count up and never overwrite an earlier file.

    The .json carries the camera's timecode and the focal length it shows
    when the log opens, so each take has its own zoom position.  Zooming
    during a take is not followed.  Set timecode to Free Run and
    gyroflow-batch-resolve places each clip in its log by timecode.

    Take logs describe the recording mode (e.g. 3840x2160 @24).  A log
    opened before the recorder is ready (at connect, or on a press it
    ignored) holds no clip and describes the HDMI monitor mode
    (3856x2170 @59.94).  gyroflow-batch-resolve sets size and frame rate
    from the clip either way.

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
