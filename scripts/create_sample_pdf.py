#!/usr/bin/env python3
"""
Simple script to create a sample PDF resume for testing
"""

import sys
from pathlib import Path

def create_sample_pdf():
    """Create a sample PDF resume using reportlab if available"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        print("reportlab not available. Install with: pip install reportlab")
        return False
    
    output_path = Path(__file__).parent.parent / "tests" / "sample_resumes" / "james_thompson_resume.pdf"
    
    # Create PDF
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "James Thompson")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 70, "Senior Engineering Manager")
    
    # Contact Info
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "Email: james.thompson@email.com | Phone: (555) 321-9876")
    c.drawString(50, height - 105, "LinkedIn: linkedin.com/in/jamesthompson | Location: San Francisco, CA")
    
    # Professional Summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 135, "Professional Summary")
    c.setFont("Helvetica", 10)
    summary = [
        "Engineering leader with 10+ years of experience managing high-performing teams",
        "and delivering complex technical initiatives. Proven track record of scaling",
        "engineering organizations while maintaining quality and team satisfaction."
    ]
    y_pos = height - 155
    for line in summary:
        c.drawString(50, y_pos, line)
        y_pos -= 15
    
    # Experience
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos - 20, "Professional Experience")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos - 45, "Senior Engineering Manager | Slack (2019-Present)")
    
    c.setFont("Helvetica", 10)
    experience = [
        "• Manage 25 engineers across 3 product teams",
        "• Responsible for platform reliability (99.99% uptime)",
        "• Led migration to microservices architecture",
        "• Grew team from 12 to 25 engineers during scale-up",
        "• Established engineering hiring processes and standards"
    ]
    y_pos -= 60
    for item in experience:
        c.drawString(50, y_pos, item)
        y_pos -= 15
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos - 20, "Engineering Manager | Dropbox (2016-2019)")
    
    c.setFont("Helvetica", 10)
    dropbox_exp = [
        "• Built and managed file sync team (15 engineers)",
        "• Delivered major storage optimization saving $2M annually",
        "• Mentored 5 engineers to senior roles",
        "• Led technical architecture decisions for storage platform"
    ]
    y_pos -= 35
    for item in dropbox_exp:
        c.drawString(50, y_pos, item)
        y_pos -= 15
    
    # Education
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos - 25, "Education")
    c.setFont("Helvetica", 10)
    c.drawString(50, y_pos - 45, "MS Computer Science - UC Berkeley (2011)")
    c.drawString(50, y_pos - 60, "BS Electrical Engineering - Georgia Tech (2009)")
    
    # Skills
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos - 90, "Technical Skills")
    c.setFont("Helvetica", 10)
    skills = [
        "Leadership: Team Management, Technical Strategy, Hiring, Performance Management",
        "Technologies: Python, Java, Distributed Systems, Microservices, AWS, Kubernetes",
        "Methodologies: Agile, Scrum, DevOps, Site Reliability Engineering"
    ]
    y_pos -= 105
    for skill in skills:
        c.drawString(50, y_pos, skill)
        y_pos -= 15
    
    # Save PDF
    c.save()
    print(f"Created sample PDF resume: {output_path}")
    return True

if __name__ == "__main__":
    success = create_sample_pdf()
    sys.exit(0 if success else 1)