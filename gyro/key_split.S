/* Per-take split with HDMI record output on.
 *
 * The fp does not track a recording state for an external recorder: no tally,
 * no state change in RAM (traced 2026-09-30).  REC and the shutter only post
 * key events, and the recorder toggles on them.  So every REC key-down (0x1E)
 * and shutter full press (0x06) closes the open H log and opens a new one:
 * each take lies inside the log its start press opened, and the logs between
 * takes are idle.  A press the recorder ignores costs one extra split, and no
 * toggle state can go out of step.  REC on the recorder itself never reaches
 * the camera.
 *
 * Site: FUN_c02dbbe8 (key post) after its queue send, so the key is already
 * delivered when the close and open run; r5 = key code there, lr is saved by
 * the function's push and no flags are live.  Runs in the posting task (the
 * key task; callers 0xC02DCE34 for REC, 0xC02DD174 for the shutter).
 * hdmi_stop and hdmi_start are the HdmiRecStop / HdmiRecStart bodies; both are
 * synchronous (take_close joins the writer before the file closes). */

.equ SITE,        0xC02DBC0C
.equ SITE_ORIG,   0xE320F000          /* nop, after bl FUN_c02dbff0 */
.equ KEY_REC_DOWN, 0x1E
.equ KEY_S2_DOWN,  0x06

    .global key_split
key_split:
    push    {r0, r1, r2, r3, ip, lr}
    cmp     r5, #KEY_REC_DOWN
    cmpne   r5, #KEY_S2_DOWN
    bne     9f
    movw    r0, #:lower16:HDMI_REC_STATE
    movt    r0, #:upper16:HDMI_REC_STATE
    ldr     r0, [r0]
    cmp     r0, #1
    bne     9f                          @ no HDMI record output: internal takes as upstream
    ldr     r0, ks_n
    add     r0, r0, #1
    str     r0, ks_n
    SHAREDAT    r0, O_T_WANT
    ldr     r0, [r0]
    cmp     r0, #0
    beq     1f
    bl      hdmi_stop
1:  bl      hdmi_start
9:  pop     {r0, r1, r2, r3, ip, lr}
    nop                                 @ the displaced instruction
    bx      lr

    .align  2
ks_n:       .word   0                   /* splits done since boot */

