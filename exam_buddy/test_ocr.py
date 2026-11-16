
import pytesseract
from PIL import Image, ImageDraw, ImageFont

# Create a high-resolution white document
image = Image.new("RGB", (1400, 400), "white")
draw = ImageDraw.Draw(image)

# Use a clear font
font = ImageFont.truetype("arial.ttf", 65)

draw.text((60, 60), "Name: Rahul Kumar", fill="black", font=font)
draw.text((60, 160), "Date of Birth: 15/08/2007", fill="black", font=font)
draw.text((60, 260), "Exam: JEE Main 2027", fill="black", font=font)

# Improve OCR configuration
text = pytesseract.image_to_string(
    image,
    config="--oem 3 --psm 6"
)

print("Extracted Information:")
print(text)
