# Bonn kidney-tubuloid annotation pilot

Protocol version: `bonn-cyst-annotation-pilot-0.1`

## Purpose and scope

This is a manual annotation usability and repeatability pilot on source images. It is not a treatment-effect analysis, model evaluation, or replication of the paper's reported measurements. The selected 24-hour images come only from development source-kidney groups. The frozen final-test group was excluded.

The source methods report QuPath 0.4.4 analysis, selecting and tracking eight random tubuloids per well in dome culture, and counting/measuring all cysts per well in suspension culture. The distributed image archive has no original object masks, per-object identities, or explicit well identifiers. The targets below are provisional operational targets and must not be described as exact source-paper reproductions without recovering and checking the supplementary object/area rules.

## Provisional annotation targets

- **Dome culture:** outline the visible outer envelope of each clearly separable whole tubuloid. Do not draw the lumen as a separate object.
- **Suspension culture:** outline each clearly separable visible cyst as its own object. Do not label an undifferentiated aggregate as a cyst when its boundary is unclear.
- Use background label `0`; assign each object a distinct positive integer label. Preserve the source image width and height. Save one single-channel integer TIFF mask per task at the `mask_path` listed in its queue.
- If an object boundary is ambiguous, partly outside the field, occluded, or not represented by a stable visible edge, do not invent the contour. Record the issue and ask for review; do not silently discard a difficult field.
- Record annotation software and version, annotator ID, segmentation method, and protocol version with each completed mask. No pixel calibration is available; report pixel geometry only until a calibration source is supplied.

## Review design

Round 1 contains one selected image per available development-kidney × culture × treatment stratum at 24 hours. Round 2 contains five differently named repeat images. Give the repeat queue to an independent reviewer when possible. If one annotator completes both rounds, separate them in time and do not reveal the repeat mapping. The assignment key is private and must be withheld until both annotation sets are frozen.

The filenames and queues conceal source treatment labels, but visible morphology may suggest a condition; this is not guaranteed blinding. The contact sheet is a low-resolution navigation aid only. Annotate the full-resolution TIFFs in `images/` and never draw on the source images.

## Handoff

After both rounds are complete, preserve original masks and hashes, use the private key to join tasks back to acquisitions, compare repeat masks, adjudicate disagreements, and update the acquisition manifest with reviewed mask paths. Keep the existing final-test kidney group untouched until the segmentation method and review rules are frozen. Importing this plan into ResearchDesk does not mark the assay measured.
