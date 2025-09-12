#!/usr/bin/env python3
"""
Simple script to create a sample resume image for OCR testing
"""

import sys
from pathlib import Path

def create_sample_image():
    """Create a simple resume image for OCR testing"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL not available. Install with: pip install pillow")
        return False
    
    output_path = Path(__file__).parent.parent / "tests" / "sample_resumes" / "john_smith_resume.png"
    
    # Create image
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font, fall back to default
    try:
        # Try common system fonts
        for font_path in ['/System/Library/Fonts/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc']:
            try:
                title_font = ImageFont.truetype(font_path, 24)
                heading_font = ImageFont.truetype(font_path, 16)
                text_font = ImageFont.truetype(font_path, 12)
                break
            except:
                continue
        else:
            # Fallback to default font
            title_font = ImageFont.load_default()
            heading_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        heading_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Draw resume content
    y_pos = 50
    
    # Title
    draw.text((50, y_pos), "John Smith", font=title_font, fill='black')
    y_pos += 40
    draw.text((50, y_pos), "Software Engineer", font=heading_font, fill='black')
    y_pos += 30
    
    # Contact
    draw.text((50, y_pos), "john.smith@email.com | (555) 111-2222", font=text_font, fill='black')
    y_pos += 20
    draw.text((50, y_pos), "GitHub: github.com/johnsmith", font=text_font, fill='black')
    y_pos += 40
    
    # Summary
    draw.text((50, y_pos), "PROFESSIONAL SUMMARY", font=heading_font, fill='black')
    y_pos += 25
    summary_lines = [
        "Experienced software engineer with 5+ years in web development.",
        "Skilled in JavaScript, Python, and cloud technologies.",
        "Strong problem-solving abilities and team collaboration skills."
    ]
    for line in summary_lines:
        draw.text((50, y_pos), line, font=text_font, fill='black')
        y_pos += 18
    y_pos += 20
    
    # Experience
    draw.text((50, y_pos), "WORK EXPERIENCE", font=heading_font, fill='black')
    y_pos += 25
    
    draw.text((50, y_pos), "Senior Developer | TechCorp (2020-Present)", font=text_font, fill='black')
    y_pos += 20
    exp_lines = [
        "• Led development of customer portal serving 10K+ users",
        "• Implemented CI/CD pipeline reducing deployment time by 50%",
        "• Mentored 3 junior developers on best practices"
    ]
    for line in exp_lines:
        draw.text((50, y_pos), line, font=text_font, fill='black')
        y_pos += 18
    y_pos += 20
    
    draw.text((50, y_pos), "Software Developer | StartupXYZ (2018-2020)", font=text_font, fill='black')
    y_pos += 20
    exp2_lines = [
        "• Built REST APIs using Node.js and Express",
        "• Developed responsive web applications with React",
        "• Collaborated with product team on feature specifications"
    ]
    for line in exp2_lines:
        draw.text((50, y_pos), line, font=text_font, fill='black')
        y_pos += 18
    y_pos += 30
    
    # Skills
    draw.text((50, y_pos), "TECHNICAL SKILLS", font=heading_font, fill='black')
    y_pos += 25
    skills_lines = [
        "Languages: JavaScript, Python, Java, TypeScript",
        "Frameworks: React, Node.js, Express, Django",
        "Tools: Git, Docker, AWS, Jenkins"
    ]
    for line in skills_lines:
        draw.text((50, y_pos), line, font=text_font, fill='black')
        y_pos += 18
    y_pos += 20
    
    # Education
    draw.text((50, y_pos), "EDUCATION", font=heading_font, fill='black')
    y_pos += 25
    draw.text((50, y_pos), "BS Computer Science - State University (2018)", font=text_font, fill='black')
    
    # Save image
    img.save(str(output_path))
    print(f"Created sample image resume: {output_path}")
    return True

if __name__ == "__main__":
    success = create_sample_image()
    sys.exit(0 if success else 1)