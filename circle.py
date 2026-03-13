import svgwrite
import cairosvg

# SVG
dwg = svgwrite.Drawing("circle.svg", size=(200, 200))
dwg.add(dwg.ellipse(center=(100, 100), r=(50, 50), stroke="black", stroke_width=2, fill="none"))
dwg.save()

cairosvg.svg2png(url="circle.svg", write_to="circle_from_svg.png", background_color="white")