"""User guide (English). Same structure and topic ids as `guide_fr.py` (a test checks it)."""

INTRO = "Everything you need to prepare your photos for Instagram with RKarrousel."

GUIDE = [
    ("start", "Getting started", [
        ("p", "RKarrousel prepares your photos for Instagram: frame, background, panorama slicing, cropping, ordering and "
              "numbering of the images. In four steps:"),
        ("steps", [
            "\"Files\" tab: add your photos with \"Add files\" or \"Add folder\" (or drag and drop them).",
            "Choose the destination folder.",
            "\"Settings\" tab: adjust the look, or pick a preset.",
            "Click \"Preview and order...\" to check and order the images, then \"Start processing\".",
        ]),
        ("note", "Your settings are saved automatically when you close the app. F1 opens this guide at any time."),
    ]),
    ("photos", "Adding photos", [
        ("bullets", [
            "Accepted formats: JPEG, PNG, TIFF and BMP.",
            "\"Add folder\" takes every image of the folder (not its subfolders).",
            "Dragging and dropping files and folders onto the list works too.",
            "Click an entry in the list: the preview on the right shows the photo, or the first photo of a folder.",
            "\"Clear selection\" empties the list.",
        ]),
        ("p", "Every photo shape is accepted: portrait, landscape, square, panorama... Processing adapts (see \"The images produced\")."),
    ]),
    ("outputs", "The images produced", [
        ("p", "Each photo gives one or more images, in the chosen output format (3:4 by default, the Instagram grid):"),
        ("bullets", [
            "Photo already in the output format: one framed image (`_framed`). It is trimmed by less than 1% so that, frame included, the format is exact.",
            "2:3 portrait, other portrait or square: the whole photo on a background of the right format (`_with_sig`, or `_framed` without a signature) and an adjustable crop (`_crop34`).",
            "3:2 landscape: the two framed halves of a panorama (`_part1`, `_part2`), the whole photo (`_part1_with_sig`) and the same rotated (`_part2_with_sig`).",
            "Other landscape or panorama: the panorama cut into contiguous slices (`_part1` to `_partN`, 10 at most), the whole photo upright and rotated, and a crop.",
        ]),
        ("note", "Panorama slices reassemble without a double border: the frame only surrounds the top, the bottom and the two ends."),
        ("p", "You do not need every image: untick a type in Settings -> \"Images produced for each photo\", "
              "or exclude one specific image in the \"Preview and order\" grid."),
    ]),
    ("look", "Frame, background and signature", [
        ("h", "Frame"),
        ("bullets", [
            "Thickness: as a percentage of the photo's shorter side (1 = thin frame, 3 = thick frame).",
            "Colour: fixed, or taken from the photo (see \"Colours taken from the photo\").",
            "\"No frame\" removes any frame; images stay exactly in the output format.",
        ]),
        ("h", "Background"),
        ("p", "When the photo is not in the output format, the rest of the image is filled with a background:"),
        ("bullets", [
            "Solid background: fixed colour (black by default) or taken from the photo.",
            "Blurred background: an enlarged, blurred version of the photo; the blur strength is adjustable.",
        ]),
        ("h", "Signature"),
        ("bullets", [
            "Choose an image (a PNG with a transparent background works best), its position (bottom right, centre or left) and its size (x).",
            "It is placed on the \"whole\" images (2:3 portraits, landscapes), not on crops nor on photos already in the right format.",
        ]),
    ]),
    ("colors", "Colours taken from the photo", [
        ("p", "The frame colour and the solid background colour can be computed for each photo:"),
        ("bullets", [
            "Photo colour: the dominant colour.",
            "Photo, light version: the dominant colour lightened (elegant for a frame).",
            "Photo, dark version: the dominant colour darkened (ideal for a solid background).",
            "Photo, complementary colour: the opposite hue, softened (a blue sky gives a warm frame, without a garish orange).",
            "Photo, contrasting colour: a light tone on a dark photo, a deep one on a light photo, in the photo's hue (a pastel or a deep brown, never pure white or black).",
        ]),
        ("p", "\"Colour taken from\" picks the reference colour: the dominant colour, the photo's edges (what the frame actually touches) or the average of the whole photo."),
        ("p", "A batch of photos with different tones thus gets frames matching each one. All images from one photo share its colours."),
        ("note", "For a single photo, the viewer (\"View large\") offers a frame colour of its own: see \"Large view and measuring\"."),
    ]),
    ("presets", "Presets", [
        ("p", "A preset remembers the frame, background, signature, format and size of the images. At the top of the Settings tab:"),
        ("bullets", [
            "Pick a preset in the list: all the settings it covers change at once.",
            "Four are provided: Classic, Black background, Photo colours, No frame. They only change the settings they mention.",
            "\"Save as...\" keeps your current settings under the name of your choice (an existing name asks for confirmation).",
            "\"Delete\" removes one of your presets; the provided presets cannot be deleted.",
        ]),
        ("note", "Changing a setting afterwards does not change the preset: save it again under the same name to update it."),
    ]),
    ("format", "Image format and size", [
        ("p", "Settings -> \"Generated files\":"),
        ("bullets", [
            "Format: 3:4 (Instagram grid, default), 4:5 (feed), 1:1 (square) or 9:16 (stories, reels). Panorama slicing, cropping and backgrounds adapt.",
            "Width: original size, or 1080 px (the ideal size for Instagram), 1440 or 2048 px. Files are much lighter, and never enlarged.",
            "JPEG quality: 100 by default; around 90-95 files are about half the size, with no visible difference.",
        ]),
        ("note", "Crop files carry the format in their name: `_crop34` in 3:4, `_crop45` in 4:5, etc."),
    ]),
    ("order", "Preview and order", [
        ("p", "The \"Preview and order...\" button shows the final rendering of every image in a three-column grid, like an Instagram profile."),
        ("bullets", [
            "The window can be enlarged: the grid keeps its three columns (like an Instagram profile) and the images grow to fill the width.",
            "Drag an image to move it: the pieces of one photo can be separated.",
            "The blue number is the one that will prefix the file (see \"File numbering\").",
            "The cross at the top right of an image excludes it (it is neither generated nor numbered); the undo arrow brings it back.",
            "Click an image to select it: \"View large\", \"Crop...\" (for a crop) and \"Exclude\" act on it. Double-click opens the crop editor, or the large view for other images. Right-click opens a menu.",
            "\"Refresh preview\" applies settings changed since opening; \"Natural order\" restores the original order.",
        ]),
    ]),
    ("crop", "Cropping an image", [
        ("p", "On a \"crop\" image, \"Crop...\" opens the editor:"),
        ("bullets", [
            "Drag the orange frame over the photo to choose the kept area; the preview on the right shows the final result.",
            "Mouse wheel or arrow keys (Shift to go faster); Top / Centre / Bottom buttons.",
            "The frame moves vertically for a photo narrower than the format, horizontally for a wider one.",
            "\"Apply\" saves the choice for this photo: it is kept from one session to the next.",
        ]),
    ]),
    ("viewer", "Large view and measuring", [
        ("p", "\"View large\" opens the full-resolution rendering:"),
        ("bullets", [
            "Wheel: zoom; drag: move the image; \"Fit\" and \"100%\" to go back.",
            "Round arrows on the edges (or the \u2190 \u2192 keys): previous or next image of the grid, without closing the window. Excluded images are skipped; the position (3 / 12) is shown at the top.",
            "Right-click + drag: a ruler that measures in pixels, for example the frame thickness.",
            "The frame thickness is also measured automatically and shown at the top.",
            "\"Settings\" panel on the right: frame thickness and colour, background (solid or blurred), signature, colours taken from the photo. What the displayed image does not use is greyed out: a panorama slice or a crop has neither background nor signature. The image is recomputed after each change, without going back to the Settings tab; the \"Settings\" button hides or shows the panel.",
            "\"This photo's frame\": a frame colour specific to the displayed photo (fixed, or taken from the photo) that replaces the general setting for that photo only. \"Same as the general settings\" cancels it. \"Resulting colour\" shows the colour actually computed for this photo; three \"Fine-tune\" sliders (hue, saturation, lightness) adjust it very slightly, by eye, for this photo only. \"Reset\" puts them back to zero. The choice is kept from one session to the next.",
            "The rest of the panel reuses the Settings tab: those apply to all photos, and the grid updates when you close the viewer.",
        ]),
    ]),
    ("numbering", "File numbering", [
        ("p", "With \"Number files\" (Settings -> \"Generated files\"), each image is prefixed with its number: 01_, 02_, 03_... "
              "(three digits beyond 99). The order is the grid's."),
        ("p", "You then copy the files to your drive or phone without renaming anything: alphabetical order is the carousel order."),
        ("note", "Running a new processing with another order in the same folder does not delete the old files: empty the folder first if needed."),
    ]),
    ("drive", "Sending to Google Drive", [
        ("p", "Settings -> \"Google Drive\": tick \"Upload images to Google Drive after processing\". Images go in numbered order to the given folder "
              "(\"Instagram/2026\" creates a subfolder; a file with the same name is updated instead of duplicated)."),
        ("h", "To do once"),
        ("steps", [
            "On console.cloud.google.com, create a project and enable \"Google Drive API\".",
            "\"OAuth consent screen\": type External, name and e-mail, then \"Publish app\" (otherwise access expires after 7 days).",
            "\"Credentials\" -> \"OAuth client ID\" -> type \"Desktop app\", then download the JSON file.",
            "In the app: \"Load credentials (JSON)...\", then \"Sign in\" (authorise in the browser; \"unverified app\": Advanced -> Continue).",
        ]),
        ("note", "The app only sees the files it uploads itself, never the rest of your Drive. The \"How to?\" button recalls these steps."),
    ]),
    ("updates", "Updates", [
        ("bullets", [
            "At every start, the app looks for a newer version on GitHub (can be disabled in Settings -> Updates).",
            "If it finds one, it shows what is new: \"Update now\", \"Later\" or \"Skip this version\".",
            "The update downloads the new version, checks that it is intact and starts, replaces the old one in place and relaunches the app.",
            "Your shortcut and settings do not change. \"Check now\" forces the check.",
        ]),
    ]),
    ("appearance", "Language and theme", [
        ("bullets", [
            "Language: French or English (Settings -> Appearance).",
            "Theme: light, dark, or \"Auto\" which follows Windows.",
        ]),
    ]),
    ("shortcuts", "Shortcuts", [
        ("bullets", [
            "F1: open this guide.",
            "Order grid: Delete excludes the selected image; Enter opens it large.",
            "Crop editor: arrows move the frame (Shift: faster); Enter applies; Esc cancels.",
            "Large view: \u2190 \u2192 previous / next image; Esc closes the window.",
        ]),
    ]),
    ("help", "If something goes wrong", [
        ("bullets", [
            "A summary is shown at the end of processing: it lists photos in error or skipped, with the reason.",
            "The log `image_splitter.log` is next to the executable (its location is shown in \"About\").",
            "\"Format too panoramic\": a very wide photo would give more than 10 images; crop it in your photo software.",
            "To start from scratch, close the app and delete the `.image_splitter_config.json` file next to the executable.",
            "To process photos without the interface: `python -m rkarrousel.cli` (see the project documentation).",
        ]),
    ]),
]
