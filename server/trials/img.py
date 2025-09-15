from PIL import Image

# Load your double intersection image
img = Image.open("images/double_intersection.jpg")

# Get current size
w, h = img.size

# Scale factor (increase width of lanes)
scale_factor = 1.3   # adjust until 3 vehicles can fit side by side

# Resize with scaling
w_new = int(w * scale_factor)
h_new = int(h * scale_factor)

# Resize image
wider_lanes = img.resize((w_new, h_new), Image.LANCZOS)

# Save the output
wider_lanes.save("images/double_intersection_wider.jpg")

print("✅ Saved as double_intersection_wider.jpg")
