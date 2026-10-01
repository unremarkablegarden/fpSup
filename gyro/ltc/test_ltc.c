/* Host test for ltc_core.h: run the encoder against a simulated video
 * timecode and write ch1 to a 48 kHz mono WAV for ltcdump.
 *
 *   cc -O2 -o test_ltc test_ltc.c && ./test_ltc out.wav [seconds] [phase]
 *
 * The simulated video timecode starts at 01:00:00:00 and advances every 2000
 * samples, `phase` samples (default 700) after each LTC frame start.  A phase
 * near 0 or 2000 puts the read on the boundary, which start_frame() has to
 * absorb. */

#include <stdio.h>
#include <stdlib.h>
#include "ltc_core.h"

#define RATE 48000
#define FPS 24
#define SPF (RATE / FPS)

static void put_le(FILE *f, uint32_t v, int n)
{
    for (int i = 0; i < n; i++)
        fputc(v >> (8 * i) & 0xFF, f);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s out.wav [seconds] [phase]\n", argv[0]);
        return 2;
    }
    uint32_t seconds = argc > 2 ? (uint32_t)atoi(argv[2]) : 60;
    uint32_t phase = argc > 3 ? (uint32_t)atoi(argv[3]) : 700;
    uint32_t total = seconds * RATE;

    struct ltc s = {0};
    s.enable = 1;
    s.amplitude = 0x2000;
    s.fps = FPS;
    s.spb = SPF / 80;

    int16_t *ring = calloc(1024 * 2, sizeof *ring);   /* one block, 2 channels */
    int16_t *out = malloc(total * sizeof *out);
    uint8_t live[4] = {1, 0, 0, 0};

    for (uint32_t done = 0; done < total; done += 1024) {
        /* The encoder reads live[] only at its own frame starts, which fall on
         * multiples of SPF; video changes `phase` samples later.  Set live to
         * what the video shows at the first sample of this block. */
        uint32_t frames = done / SPF + (done % SPF >= phase ? 1 : 0);
        uint32_t tc = 0x01000000;
        for (uint32_t i = 0; i < frames; i++)
            tc = tc_inc(tc, FPS);
        live[0] = tc >> 24;
        live[1] = tc >> 16;
        live[2] = tc >> 8;
        live[3] = tc;

        ltc_fill(&s, ring, 2, 1024, live);
        for (uint32_t i = 0; i < 1024 && done + i < total; i++)
            out[done + i] = ring[2 * i];
    }

    FILE *f = fopen(argv[1], "wb");
    if (!f) {
        perror(argv[1]);
        return 1;
    }
    fwrite("RIFF", 1, 4, f);
    put_le(f, 36 + total * 2, 4);
    fwrite("WAVEfmt ", 1, 8, f);
    put_le(f, 16, 4);
    put_le(f, 1, 2);
    put_le(f, 1, 2);
    put_le(f, RATE, 4);
    put_le(f, RATE * 2, 4);
    put_le(f, 2, 2);
    put_le(f, 16, 2);
    fwrite("data", 1, 4, f);
    put_le(f, total * 2, 4);
    fwrite(out, 2, total, f);
    fclose(f);
    return 0;
}
