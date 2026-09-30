/* REC trace: which RAM words change when the fp's REC button is pressed with
 * HDMI RAW out.  Diagnostic build only (edition `trace`); not in a release.
 *
 * Called from accel_hook (~47 Hz) while a log is open.  Each call compares the
 * regions below with their copy from the previous call and appends one record
 * per changed word:
 *
 *      0   u16  key     region << 12 | word index in the region
 *      2   u16  value, low half
 *      4   i16  tag     TAG_TRACE
 *      6   u16  value, high half
 *
 * The record lands after the drain, so its position in the stream dates it to
 * the accelerometer sample, like tag 1.  Decode with trace_decode.py.
 *
 * When a new take opens (W_OPENS changed), every copy is set to the bitwise NOT
 * of the live word and nothing is emitted, so the following calls dump every
 * word once: each log starts with a full baseline.  At most TRACE_CAP records
 * per call; words not emitted keep their old copy and go out on a later call.
 * A failed claim (no free block) ends the call the same way.
 *
 * Copies live at pool + TRACE_POOL_OFF, one word per traced word, in region
 * order (3536 bytes, one page).  The W_OPENS value last seen is t_opens, in the
 * blob: the pool page keeps its contents across a power cycle, the blob is
 * copied in fresh at every boot, so the first call after boot always
 * rebaselines.
 *
 * Also here: marker hooks (MARK below), armed by trace_arm from gsup_boot.
 * Each call while a log is open appends a TAG_MARK record, x = marker id,
 * y = a, z = b (low halves), and, when the marker knows its caller, a
 * TAG_MARK_LR record, x = marker id, y/z = caller return address low/high.
 * At most MARK_CAP calls per marker per take.
 */

.equ TRACE_POOL_OFF, 0x41000        /* one page below FOBJ_POOL_OFF           */
.equ TRACE_CAP,      48
.equ TAG_TRACE,      0x10           /* imu_stream.py claims 0-5               */
.equ TAG_MARK,       0x11
.equ TAG_MARK_LR,    0x12
.equ MARK_N,         8
.equ MARK_CAP,       2000

/* The regions.  Keys 0-3; see trace_decode.py for the same table. */
.equ TR0_BASE, 0xC3033834           /* system state, FUN_c00178d8().  +0x18+0x204
                                     * = HDMI rec output, +0x18+0x220 = capture
                                     * state (GetCamStatus)                   */
.equ TR0_WORDS, 500                 /* 0x7D0 bytes                            */
.equ TR1_BASE, 0xC3464980           /* lens data (FUN_c03341c8 singleton)     */
.equ TR1_WORDS, 128
.equ TR2_BASE, 0xC307CD80           /* lens calibration block; DIST_FOCAL at
                                     * 0xC307CDF0, support axis at 0xC307CE2C */
.equ TR2_WORDS, 128
.equ TR3_BASE, 0xC3464B80           /* lens data, continued                   */
.equ TR3_WORDS, 128

.macro TRACE_REGION base, words, region
    movw    r5, #:lower16:\base
    movt    r5, #:upper16:\base
    movw    r6, #\words
    mov     r7, #(\region << 12)
    bl      trace_region
    cmp     r9, #0
    beq     9f                          @ budget spent or stream full
.endm

    .global trace_diff
trace_diff:
    push    {r4, r5, r6, r7, r8, r9, r10, r11, ip, lr}
    BLOBBASE r11
    sub     r10, r11, #(CODE_POOL_OFF - TRACE_POOL_OFF)
    ldr     r0, [r11, #O_W_OPENS]
    ldr     r1, t_opens
    mov     r8, #0
    cmp     r0, r1
    beq     1f
    str     r0, t_opens
    mov     r8, #1                      @ new take: rebaseline, emit nothing
    adr     r1, mark_hits               @ and give every marker its cap again
    mov     r2, #0
    mov     r3, #MARK_N
2:  str     r2, [r1], #4
    subs    r3, r3, #1
    bne     2b
1:  mov     r9, #TRACE_CAP

    TRACE_REGION TR0_BASE, TR0_WORDS, 0
    TRACE_REGION TR1_BASE, TR1_WORDS, 1
    TRACE_REGION TR2_BASE, TR2_WORDS, 2
    TRACE_REGION TR3_BASE, TR3_WORDS, 3

9:  pop     {r4, r5, r6, r7, r8, r9, r10, r11, ip, lr}
    bx      lr

/* r5 = live words, r6 = count, r7 = first key, r8 = rebaseline,
 * r9 = budget (0 on return = stop), r10 = copy cursor (advanced past the
 * region unless the call stopped). */
trace_region:
    push    {r4, lr}
1:  ldr     r0, [r5], #4
    cmp     r8, #0
    mvnne   r0, r0
    strne   r0, [r10]
    bne     3f
    ldr     r1, [r10]
    cmp     r0, r1
    beq     3f
    mov     r4, r0
    mov     r0, #1
    bl      stream_claim                @ r0 = where, r1 = how many
    cmp     r1, #0
    moveq   r9, #0
    beq     8f
    strh    r7, [r0]
    strh    r4, [r0, #2]
    lsr     r1, r4, #16
    strh    r1, [r0, #6]
    mov     r1, #TAG_TRACE
    strh    r1, [r0, #4]                @ last: the tag publishes the record
    mov     r0, #1
    bl      stream_commit
    str     r4, [r10]
    subs    r9, r9, #1
    beq     8f
3:  add     r10, r10, #4
    add     r7, r7, #1
    subs    r6, r6, #1
    bne     1b
8:  pop     {r4, lr}
    bx      lr

    .align  2
t_opens:    .word   0xFFFFFFFF
mark_hits:  .space  (MARK_N * 4)

/* ------------------------------------------------------------ markers */

/* Each site is after its function's push (lr saved), and no flags set before
 * the site are read after it: the body's cmp would clobber them.  The body
 * runs the displaced instruction last, after restoring r0-r3, ip, lr. */
.equ MK0_SITE, 0xC04A6724       /* FUN_c04a6720 HDMI connect handler: sub sp, sp, #0x14 */
.equ MK1_SITE, 0xC04A6A2C       /* FUN_c04a6a20, HdmiRecStop caller: ldr r4, [r0, #0x204] */
.equ MK2_SITE, 0xC037218C       /* recorder vtable +0x50 (set, r1 = arg): sub sp, sp, #0xbc */
.equ MK3_SITE, 0xC037237C       /* recorder vtable +0x54: sub sp, sp, #0xbc */
.equ MK4_SITE, 0xC03723CC       /* recorder vtable +0x58: sub sp, sp, #0xbc */
.equ MK5_SITE, 0xC0372414       /* recorder vtable +0x5c (get): mov r4, r0 */
.equ MK6_SITE, 0xC02DBBEC       /* FUN_c02dbbe8 key post (r1 = key code): sub sp, sp, #4 */
.equ MK7_SITE, 0xC0017F0C       /* FUN_c0017f08 capture struct setter (r1 = new
                                 * copy of captureState+0x1F4): sub sp, sp, #8 */

/* Body: push six words, then \setup leaves a in r0, b in r1, caller lr (or 0)
 * in r3.  The function's own push sits above ours at sp + 24. */
.macro MARK id, setup, displaced:vararg
mark_\id:
    push    {r0, r1, r2, r3, ip, lr}
    \setup
    mov     r2, #\id
    bl      mark_emit
    pop     {r0, r1, r2, r3, ip, lr}
    \displaced
    bx      lr
.endm

.macro ARGS_R0R1
    mov     r3, #0
.endm
/* push {r4, r5, lr}: caller lr at +8 */
.macro ARGS_KEY
    ldr     r3, [sp, #(24 + 8)]
    mov     r0, r1
    mov     r1, #0
.endm
/* push {r4, r5, r6, lr}: caller lr at +12.  Fields +0x2C and +0x3C of the
 * copy are captureState+0x220 (capture state) and +0x230 (press count). */
.macro ARGS_CAPTURE
    ldr     r3, [sp, #(24 + 12)]
    ldr     r0, [r1, #0x2C]
    ldr     r1, [r1, #0x3C]
.endm

    MARK 0, ARGS_R0R1, sub sp, sp, #0x14
    MARK 1, ARGS_R0R1, ldr r4, [r0, #0x204]
    MARK 2, ARGS_R0R1, sub sp, sp, #0xbc
    MARK 3, ARGS_R0R1, sub sp, sp, #0xbc
    MARK 4, ARGS_R0R1, sub sp, sp, #0xbc
    MARK 5, ARGS_R0R1, mov r4, r0
    MARK 6, ARGS_KEY, sub sp, sp, #4
    MARK 7, ARGS_CAPTURE, sub sp, sp, #8

/* r0 = a, r1 = b, r2 = marker id, r3 = caller lr or 0. */
mark_emit:
    push    {r4, r5, r6, r7, r8, lr}
    mov     r4, r0
    mov     r5, r1
    mov     r6, r2
    mov     r7, r3
    SHAREDAT    ip, O_T_WANT
    ldr     ip, [ip]
    cmp     ip, #0
    beq     9f
    adr     r3, mark_hits
    ldr     r0, [r3, r6, lsl #2]
    cmp     r0, #MARK_CAP
    bhs     9f
    add     r0, r0, #1
    str     r0, [r3, r6, lsl #2]
    mov     r0, #1
    bl      stream_claim                @ keeps r2-r6
    cmp     r1, #0
    beq     9f
    strh    r6, [r0]
    strh    r4, [r0, #2]
    strh    r5, [r0, #6]
    mov     r1, #TAG_MARK
    strh    r1, [r0, #4]                @ last: the tag publishes the record
    mov     r0, #1
    bl      stream_commit
    cmp     r7, #0
    beq     9f
    mov     r0, #1
    bl      stream_claim
    cmp     r1, #0
    beq     9f
    strh    r6, [r0]
    strh    r7, [r0, #2]
    lsr     r1, r7, #16
    strh    r1, [r0, #6]
    mov     r1, #TAG_MARK_LR
    strh    r1, [r0, #4]
    mov     r0, #1
    bl      stream_commit
9:  pop     {r4, r5, r6, r7, r8, pc}

/* Called from gsup_boot, r6 = blob base, as s_hook expects. */
.macro ARM id
    adr     r0, mark_\id
    sub     r0, r0, r6
    movw    r1, #:lower16:MK\id\()_SITE
    movt    r1, #:upper16:MK\id\()_SITE
    bl      s_hook
.endm

    .global trace_arm
trace_arm:
    push    {r4, lr}
    ARM 0
    ARM 1
    ARM 2
    ARM 3
    ARM 4
    ARM 5
    ARM 6
    ARM 7
    pop     {r4, pc}
