from PIL import Image, ImageDraw

sizes = [72, 96, 128, 144, 152, 192, 384, 512]

for size in sizes:
    # Create gradient
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    
    # Draw gradient background (simple solid for now)
    draw.rectangle([0, 0, size, size], fill='#00f5ff')
    
    # Draw checkmark
    draw.text((size//4, size//4), '✓', fill='#0f0c29')
    
    # Save
    img.save(f'icon-{size}x{size}.png')
    print(f'✅ Created icon-{size}x{size}.png')

print('🎉 All icons generated!')