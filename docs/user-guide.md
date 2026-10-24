<!-- Généré par tools/build_docs.py à partir de rkarrousel/i18n/guide_en.py : ne pas modifier à la main. -->
# RKarrousel user guide

Everything you need to prepare your photos for Instagram with RKarrousel.

## Contents

1. [Getting started](#getting-started)
2. [Adding photos](#adding-photos)
3. [The images produced](#the-images-produced)
4. [Frame, background and signature](#frame-background-and-signature)
5. [Colours taken from the photo](#colours-taken-from-the-photo)
6. [Presets](#presets)
7. [Image format and size](#image-format-and-size)
8. [Preview and order](#preview-and-order)
9. [Cropping an image](#cropping-an-image)
10. [Large view and measuring](#large-view-and-measuring)
11. [File numbering](#file-numbering)
12. [Sending to Google Drive](#sending-to-google-drive)
13. [Updates](#updates)
14. [Language and theme](#language-and-theme)
15. [Shortcuts](#shortcuts)
16. [If something goes wrong](#if-something-goes-wrong)

## Getting started

RKarrousel prepares your photos for Instagram: frame, background, panorama slicing, cropping, ordering and numbering of the images. In four steps:

1. "Files" tab: add your photos with "Add files" or "Add folder" (or drag and drop them).
2. Choose the destination folder.
3. "Settings" tab: adjust the look, or pick a preset.
4. Click "Preview and order..." to check and order the images, then "Start processing".

> **Note** — Your settings are saved automatically when you close the app. F1 opens this guide at any time.


## Adding photos

- Accepted formats: JPEG, PNG, TIFF and BMP.
- "Add folder" takes every image of the folder (not its subfolders).
- Dragging and dropping files and folders onto the list works too.
- Click an entry in the list: the preview on the right shows the photo, or the first photo of a folder.
- "Clear selection" empties the list.

Every photo shape is accepted: portrait, landscape, square, panorama... Processing adapts (see "The images produced").


## The images produced

Each photo gives one or more images, in the chosen output format (3:4 by default, the Instagram grid):

- Photo already in the output format: one framed image (`_framed`). It is trimmed by less than 1% so that, frame included, the format is exact.
- 2:3 portrait, other portrait or square: the whole photo on a background of the right format (`_with_sig`, or `_framed` without a signature) and an adjustable crop (`_crop34`).
- 3:2 landscape: the two framed halves of a panorama (`_part1`, `_part2`), the whole photo (`_part1_with_sig`) and the same rotated (`_part2_with_sig`).
- Other landscape or panorama: the panorama cut into contiguous slices (`_part1` to `_partN`, 10 at most), the whole photo upright and rotated, and a crop.

> **Note** — Panorama slices reassemble without a double border: the frame only surrounds the top, the bottom and the two ends.

You do not need every image: untick a type in Settings -> "Images produced for each photo", or exclude one specific image in the "Preview and order" grid.


## Frame, background and signature

### Frame

- Thickness: as a percentage of the photo's shorter side (1 = thin frame, 3 = thick frame).
- Colour: fixed, or taken from the photo (see "Colours taken from the photo").
- "No frame" removes any frame; images stay exactly in the output format.

### Background

When the photo is not in the output format, the rest of the image is filled with a background:

- Solid background: fixed colour (black by default) or taken from the photo.
- Blurred background: an enlarged, blurred version of the photo; the blur strength is adjustable.

### Signature

- Choose an image (a PNG with a transparent background works best), its position (bottom right, centre or left) and its size (x).
- It is placed on the "whole" images (2:3 portraits, landscapes), not on crops nor on photos already in the right format.


## Colours taken from the photo

The frame colour and the solid background colour can be computed for each photo:

- Photo colour: the dominant colour.
- Photo, light version: the dominant colour lightened (elegant for a frame).
- Photo, dark version: the dominant colour darkened (ideal for a solid background).

A batch of photos with different tones thus gets frames matching each one. All images from one photo share its colours.


## Presets

A preset remembers the frame, background, signature, format and size of the images. At the top of the Settings tab:

- Pick a preset in the list: all the settings it covers change at once.
- Four are provided: Classic, Black background, Photo colours, No frame. They only change the settings they mention.
- "Save as..." keeps your current settings under the name of your choice (an existing name asks for confirmation).
- "Delete" removes one of your presets; the provided presets cannot be deleted.

> **Note** — Changing a setting afterwards does not change the preset: save it again under the same name to update it.


## Image format and size

Settings -> "Generated files":

- Format: 3:4 (Instagram grid, default), 4:5 (feed), 1:1 (square) or 9:16 (stories, reels). Panorama slicing, cropping and backgrounds adapt.
- Width: original size, or 1080 px (the ideal size for Instagram), 1440 or 2048 px. Files are much lighter, and never enlarged.
- JPEG quality: 100 by default; around 90-95 files are about half the size, with no visible difference.

> **Note** — Crop files carry the format in their name: `_crop34` in 3:4, `_crop45` in 4:5, etc.


## Preview and order

The "Preview and order..." button shows the final rendering of every image in a three-column grid, like an Instagram profile.

- Drag an image to move it: the pieces of one photo can be separated.
- The blue number is the one that will prefix the file (see "File numbering").
- The cross at the top right of an image excludes it (it is neither generated nor numbered); the undo arrow brings it back.
- Click an image to select it: "View large", "Crop..." (for a crop) and "Exclude" act on it. Double-click opens the crop editor, or the large view for other images. Right-click opens a menu.
- "Refresh preview" applies settings changed since opening; "Natural order" restores the original order.


## Cropping an image

On a "crop" image, "Crop..." opens the editor:

- Drag the orange frame over the photo to choose the kept area; the preview on the right shows the final result.
- Mouse wheel or arrow keys (Shift to go faster); Top / Centre / Bottom buttons.
- The frame moves vertically for a photo narrower than the format, horizontally for a wider one.
- "Apply" saves the choice for this photo: it is kept from one session to the next.


## Large view and measuring

"View large" opens the full-resolution rendering:

- Wheel: zoom; drag: move the image; "Fit" and "100%" to go back.
- Right-click + drag: a ruler that measures in pixels, for example the frame thickness.
- The frame thickness is also measured automatically and shown at the top.
- "Settings" panel on the right: frame thickness and colour, background (solid or blurred), signature, colours taken from the photo. What the displayed image does not use is greyed out: a panorama slice or a crop has neither background nor signature. The image is recomputed after each change, without going back to the Settings tab; the "Settings" button hides or shows the panel.
- These are the settings of the Settings tab: they apply to all photos, and the grid updates when you close the viewer.


## File numbering

With "Number files" (Settings -> "Generated files"), each image is prefixed with its number: 01_, 02_, 03_... (three digits beyond 99). The order is the grid's.

You then copy the files to your drive or phone without renaming anything: alphabetical order is the carousel order.

> **Note** — Running a new processing with another order in the same folder does not delete the old files: empty the folder first if needed.


## Sending to Google Drive

Settings -> "Google Drive": tick "Upload images to Google Drive after processing". Images go in numbered order to the given folder ("Instagram/2026" creates a subfolder; a file with the same name is updated instead of duplicated).

### To do once

1. On console.cloud.google.com, create a project and enable "Google Drive API".
2. "OAuth consent screen": type External, name and e-mail, then "Publish app" (otherwise access expires after 7 days).
3. "Credentials" -> "OAuth client ID" -> type "Desktop app", then download the JSON file.
4. In the app: "Load credentials (JSON)...", then "Sign in" (authorise in the browser; "unverified app": Advanced -> Continue).

> **Note** — The app only sees the files it uploads itself, never the rest of your Drive. The "How to?" button recalls these steps.


## Updates

- At every start, the app looks for a newer version on GitHub (can be disabled in Settings -> Updates).
- If it finds one, it shows what is new: "Update now", "Later" or "Skip this version".
- The update downloads the new version, checks that it is intact and starts, replaces the old one in place and relaunches the app.
- Your shortcut and settings do not change. "Check now" forces the check.


## Language and theme

- Language: French or English (Settings -> Appearance).
- Theme: light, dark, or "Auto" which follows Windows.


## Shortcuts

- F1: open this guide.
- Order grid: Delete excludes the selected image; Enter opens it large.
- Crop editor: arrows move the frame (Shift: faster); Enter applies; Esc cancels.
- Large view: Esc closes the window.


## If something goes wrong

- A summary is shown at the end of processing: it lists photos in error or skipped, with the reason.
- The log `image_splitter.log` is next to the executable (its location is shown in "About").
- "Format too panoramic": a very wide photo would give more than 10 images; crop it in your photo software.
- To start from scratch, close the app and delete the `.image_splitter_config.json` file next to the executable.
- To process photos without the interface: `python -m rkarrousel.cli` (see the project documentation).
