from PIL import Image
import sys

path = sys.argv[1]
img = Image.open(path).convert('RGB')
width, height = img.size
px = img.load()

# consider pixel white if all channels >= threshold
TH = 250

def is_white(x, y):
    r, g, b = px[x, y]
    return r >= TH and g >= TH and b >= TH

# scan from each side

def scan_top():
    for y in range(height//2):
        if any(not is_white(x, y) for x in range(width)):
            return y
    return height//2

def scan_bottom():
    for i in range(height//2):
        y = height - 1 - i
        if any(not is_white(x, y) for x in range(width)):
            return i
    return height//2

def scan_left():
    for x in range(width//2):
        if any(not is_white(x, y) for y in range(height)):
            return x
    return width//2

def scan_right():
    for i in range(width//2):
        x = width - 1 - i
        if any(not is_white(x, y) for y in range(height)):
            return i
    return width//2

top = scan_top()
bottom = scan_bottom()
left = scan_left()
right = scan_right()

# border thickness as min of sides (in pixels)
border_px = min(top, bottom, left, right)

print(f"file={path}")
print(f"size={width}x{height}")
print(f"top={top}, bottom={bottom}, left={left}, right={right}")
print(f"border_px={border_px}")
print(f"border_ratio_w={border_px/width:.6f}")
print(f"border_ratio_h={border_px/height:.6f}")
print(f"border_ratio_min={border_px/min(width,height):.6f}")
