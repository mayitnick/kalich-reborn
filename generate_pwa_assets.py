import os
from PIL import Image, ImageDraw, ImageFont

def generate_icons():
    os.makedirs('pwa/icons', exist_ok=True)
    
    # Create a nice base image for 512x512
    size = 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a premium gradient-like background circle
    # We will draw nested circles with slightly different colors or a rounded rect
    # Let's draw a rounded rectangle with a nice sleek dark/orange theme
    box = [(16, 16), (496, 496)]
    # Background: nice deep dark purple/blue color #1e1e2e
    draw.rounded_rectangle(box, radius=100, fill=(30, 30, 46, 255), outline=(245, 194, 231, 255), width=8)
    
    # Draw a stylized fox silhouette or schedule symbol
    # Let's draw a nice bright orange fox head / triangle structure
    # Ears
    draw.polygon([(160, 200), (220, 120), (240, 220)], fill=(250, 179, 135, 255)) # Left ear
    draw.polygon([(352, 200), (292, 120), (272, 220)], fill=(250, 179, 135, 255)) # Right ear
    
    # Face base
    draw.polygon([(150, 220), (362, 220), (256, 380)], fill=(249, 139, 168, 255)) # Main face wedge
    # White cheeks
    draw.polygon([(150, 220), (210, 280), (256, 320)], fill=(205, 214, 244, 255))
    draw.polygon([(362, 220), (302, 280), (256, 320)], fill=(205, 214, 244, 255))
    
    # Nose
    draw.polygon([(240, 350), (272, 350), (256, 380)], fill=(17, 17, 27, 255))
    
    # Eyes
    draw.ellipse([(200, 220), (220, 240)], fill=(17, 17, 27, 255))
    draw.ellipse([(292, 220), (312, 240)], fill=(17, 17, 27, 255))
    
    # Save the 512x512 version
    image.save('pwa/icons/icon-512.png', 'PNG')
    print("Generated pwa/icons/icon-512.png")
    
    # Resize and save the 192x192 version
    image_192 = image.resize((192, 192), Image.Resampling.LANCZOS)
    image_192.save('pwa/icons/icon-192.png', 'PNG')
    print("Generated pwa/icons/icon-192.png")

if __name__ == '__main__':
    generate_icons()
