# PointSpeak Privacy Model

PointSpeak captures sensitive context: screen pixels, DOM metadata, annotations, and eventually audio/transcripts.

Initial defaults:

- Local receiver only.
- No cloud upload by default.
- Visible user-triggered capture.
- No cookies or authorization headers.
- No network bodies in MVP.
- Mask password/payment/token-like inputs.
- Respect `data-pointspeak-mask`, `data-pointspeak-block`, and `data-pointspeak-ignore`.
- Emit `privacy-report.json` in each bundle.
