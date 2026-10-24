"""User guide (English). Same structure and topic ids as `guide_fr.py` (a test checks it)."""

INTRO = "Everything you need to prepare your photos for Instagram with RKarrousel."

GUIDE = [
    ("start", "Getting started", [
        ("p", "RKarrousel prepares your photos for Instagram: frame, background, panorama slicing, cropping, ordering and "
              "numbering of the images. The app is a four-step flow, from left to right:"),
        ("steps", [
            "\"Photos\": add your photos (or drag and drop them), choose the destination folder and the image format.",
            "\"Order\": the grid shows every image produced; reorder them, exclude the ones you do not want, crop.",
            "\"Adjust\": image by image, set frame, colours, background and signature, and judge the result as a carousel.",
            "\"Export\": file quality and size, numbering, Google Drive, then \"Start processing\".",
        ]),
        ("note", "The \"Previous\" and \"Next\" buttons at the bottom move you along; you can also click a step you have already reached at the top. "
                 "Your settings are saved automatically when you close the app, and F1 opens this guide at any time."),
    ]),
    ("photos", "Step 1: Photos", [
        ("bullets", [
            "Accepted formats: JPEG, PNG, TIFF and BMP. Every photo shape works: portrait, landscape, square, panorama...",
            "\"Add folder\" takes every image of the folder (not its subfolders).",
            "Dragging and dropping files and folders onto the list works too.",
            "Click an entry in the list: the preview on the right shows the photo, or the first photo of a folder. To remove one photo: the \u2715 on its row, the Delete key or \"Remove\"; \"Clear all\" empties the list.",
            "Image format: 3:4 (Instagram grid, default), 4:5 (feed), 1:1 (square) or 9:16 (stories, reels). Pick it first: panorama slicing, cropping and backgrounds adapt.",
            "\"Next\" becomes available as soon as there is at least one photo and a destination folder.",
        ]),
    ]),
    ("outputs", "The images produced", [
        ("p", "Each photo gives one or more images, in the chosen output format:"),
        ("bullets", [
            "Photo already in the output format: one framed image (`_framed`). It is trimmed by less than 1% so that, frame included, the format is exact.",
            "2:3 portrait, other portrait or square: the whole photo on a background of the right format (`_with_sig`, or `_framed` without a signature) and an adjustable crop (`_crop34`).",
            "3:2 landscape: the two framed halves of a panorama (`_part1`, `_part2`), the whole photo (`_part1_with_sig`) and the same rotated (`_part2_with_sig`).",
            "Other landscape or panorama: the panorama cut into contiguous slices (`_part1` to `_partN`, 20 at most), the whole photo upright and rotated, and a crop.",
        ]),
        ("p", "With a solid background (black by default) as with a blurred one, the frame surrounds the whole image, at its edge; the whole photo sits inside it."),
        ("note", "Panorama slices reassemble without a double border: the frame only surrounds the top, the bottom and the two ends."),
        ("p", "You do not need every image: untick a type in the \"Images produced\" column of the Order step, "
              "or exclude one specific image with the cross on its tile."),
    ]),
    ("order", "Step 2: Order", [
        ("p", "The grid shows the final rendering of every image, like an Instagram profile. The order reads left to right, row after row."),
        ("bullets", [
            "Drag an image to move it: the pieces of one photo can be separated.",
            "Enlarge the window to see more images at once: the grid adds columns (three at minimum).",
            "The blue number is the one that will prefix the file (see \"File numbering\").",
            "Instagram limits a carousel to 20 images: beyond that, an orange warning appears at the top and the numbers of images 21 onwards turn red. Exclude some or split them across several posts.",
            "The cross at the top right of an image excludes it (it is neither generated nor numbered); the undo arrow brings it back.",
            "Click an image to select it: \"Adjust this image\" opens the next step on it, \"Crop...\" adjusts a crop, \"Exclude\" removes it. Double-click opens the crop editor, or the adjustments for other images. Right-click opens a menu.",
            "\"Images produced\" column: tick the image types you want for each photo. For a landscape, the two whole photos (upright and rotated) go before or after the split, at the end of the carousel (in photo order), or are removed. By default the whole photo comes before the slices.",
            "\"Refresh preview\" applies settings changed elsewhere; \"Natural order\" restores the original order.",
        ]),
    ]),
    ("adjust", "Step 3: Adjust", [
        ("p", "The selected image is shown in full resolution, with its neighbours on either side, like when you swipe through an Instagram post."),
        ("bullets", [
            "Wheel: zoom; drag: move the zoomed image; \"Fit\" and \"100%\" to go back.",
            "Round arrows on the edges (or the ← → keys): previous or next image of the grid. Excluded images are skipped; the position (3 / 12) is shown at the top.",
            "Dragging the image with the mouse slides it: released far enough (or with a quick flick), the neighbouring image slides in; otherwise it springs back.",
            "Browsing is fast: neighbours and the preview of the new image show up immediately, then full resolution sharpens as soon as you stop.",
            "The \"Carousel\" box shows or hides the neighbouring images; \"Crop...\" opens the framing editor when the displayed image is a crop.",
            "Right-click + drag: a ruler that measures in pixels, for example the frame thickness, also measured automatically and shown at the top.",
            "Right-hand panel: presets, frame, background, signature. The image is recomputed after each change; what the displayed image does not use is greyed out (a panorama slice or a crop has neither background nor signature). These settings apply to all photos.",
            "\"This photo's frame\": a frame colour specific to the displayed photo (fixed, or taken from the photo) that replaces the general setting for that photo only. \"Same as the general settings\" cancels it. \"Resulting colour\" shows the colour actually computed; three \"Fine-tune\" sliders (hue, saturation, lightness) adjust it very slightly, by eye. \"Reset\" puts them back to zero; double-clicking a row puts that one slider back in the middle.",
        ]),
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
        ("note", "For a single photo, the Adjust step offers a frame colour of its own, with a fine-tune."),
    ]),
    ("presets", "Presets", [
        ("p", "A preset remembers the frame, background, signature, format and size of the images. They are at the top of the Adjust step's panel:"),
        ("bullets", [
            "Pick a preset in the list: all the settings it covers change at once.",
            "Four are provided: Classic, Black background, Photo colours, No frame. They only change the settings they mention.",
            "\"Save as...\" keeps your current settings under the name of your choice (an existing name asks for confirmation).",
            "\"Delete\" removes one of your presets; the provided presets cannot be deleted.",
        ]),
        ("note", "Changing a setting afterwards does not change the preset: save it again under the same name to update it."),
    ]),
    ("crop", "Cropping an image", [
        ("p", "On a \"crop\" image, \"Crop...\" (Order or Adjust step) opens the editor:"),
        ("bullets", [
            "Drag the orange frame over the photo to choose the kept area; the preview on the right shows the final result.",
            "Mouse wheel or arrow keys (Shift to go faster); Top / Centre / Bottom buttons.",
            "The frame moves vertically for a photo narrower than the format, horizontally for a wider one.",
            "\"Apply\" saves the choice for this photo: it is kept from one session to the next.",
        ]),
    ]),
    ("export", "Step 4: Export", [
        ("p", "The summary announces what is about to be produced (number of images, excluded ones, destination) and warns beyond 20 images."),
        ("bullets", [
            "Width: original size, or 1080 px (the ideal size for Instagram), 1440 or 2048 px. Files are much lighter, and never enlarged.",
            "JPEG quality: 100 by default; around 90-95 files are about half the size, with no visible difference.",
            "\"Number files\" prefixes each image with its number (see \"File numbering\").",
            "Google Drive: automatic upload after processing (see \"Sending to Google Drive\").",
            "\"Start processing\" (at the bottom) produces the files; \"Cancel\" stops it. A summary is shown at the end.",
        ]),
        ("note", "Crop files carry the format in their name: `_crop34` in 3:4, `_crop45` in 4:5, etc."),
    ]),
    ("numbering", "File numbering", [
        ("p", "With \"Number files\" (Export step), each image is prefixed with its number: 01_, 02_, 03_... "
              "(three digits beyond 99). The order is the Order step's."),
        ("p", "You then copy the files to your drive or phone without renaming anything: alphabetical order is the carousel order."),
        ("note", "Running a new processing with another order in the same folder does not delete the old files: empty the folder first if needed."),
    ]),
    ("drive", "Sending to Google Drive", [
        ("p", "Export step -> \"Google Drive\": tick \"Upload images to Google Drive after processing\". Images go in numbered order to the given folder "
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
    ("preferences", "Preferences and updates", [
        ("bullets", [
            "The \"Preferences\" button (top right) sets the language (English or French), the theme (light, dark, or \"Auto\" which follows Windows) and updates.",
            "At every start, the app looks for a newer version on GitHub (can be disabled in the preferences) and shows what is new in your language.",
            "\"Update now\" downloads the new version, checks that it is intact and starts, replaces the old one in place and relaunches the app; \"Later\" or \"Skip this version\" postpone it.",
            "Your shortcut and settings do not change. \"Check now\" forces the check.",
        ]),
    ]),
    ("shortcuts", "Shortcuts", [
        ("bullets", [
            "F1: open this guide.",
            "Photo list: Delete removes the selected photo.",
            "Order grid: Delete excludes the selected image; Enter opens it in the adjustments.",
            "Adjust: ← → previous / next image.",
            "Crop editor: arrows move the frame (Shift: faster); Enter applies; Esc cancels.",
        ]),
    ]),
    ("help", "If something goes wrong", [
        ("bullets", [
            "A summary is shown at the end of processing: it lists photos in error or skipped, with the reason.",
            "The log `image_splitter.log` is next to the executable (its location is shown in \"About\").",
            "\"Format too panoramic\": a very wide photo would give more than 20 images (an Instagram carousel's limit); crop it in your photo software.",
            "To start from scratch, close the app and delete the `.image_splitter_config.json` file next to the executable.",
            "To process photos without the interface: `python -m rkarrousel.cli` (see the project documentation).",
        ]),
    ]),
]
