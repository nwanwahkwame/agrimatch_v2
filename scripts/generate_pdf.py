import os
import re
from fpdf import FPDF

class AgriMatchGuidePDF(FPDF):
    def header(self):
        # Only print header if not page 1 (cover is page 1)
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(122, 144, 136)
            self.cell(0, 10, "AgriMatch Web Interface User Guide & Tutorial", align="R")
            self.ln(10)
            self.set_draw_color(200, 216, 210)
            self.line(10, 18, 200, 18)
            self.ln(2)

    def footer(self):
        # Position footer at 15 mm from bottom
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(122, 144, 136)
        if self.page_no() > 1:
            # Page number
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

def clean_text(text):
    # Replace common markdown/HTML entity patterns
    replacements = {
        "&rsaquo;": ">",
        "&rsquo;": "'",
        "&lsquo;": "'",
        "&ldquo;": '"',
        "&rdquo;": '"',
        "&apos;": "'",
        "&nbsp;": " ",
        "&middot;": "*",
        "&bull;": "*",
        "&rarr;": "->",
        "&larr;": "<-",
        "&deg;": " degrees",
        "&le;": "<=",
        "&ge;": ">=",
        "&quot;": '"',
        "&amp;": "&",
        "&times;": "x",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": " - ",
        "…": "...",
        "\u203a": ">",
        "\u2013": "-",
        "\u2014": " - ",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\xa0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Encode as latin-1, replacing unsupported chars with empty or standard character
    return text.encode("latin-1", "replace").decode("latin-1")

def build_pdf():
    workspace_dir = r"c:\Users\GOLDEN\Desktop\agrimatch"
    md_path = os.path.join(workspace_dir, "docs", "web_interface_guide.md")
    output_pdf_path = os.path.join(workspace_dir, "docs", "web_interface_guide.pdf")

    if not os.path.exists(md_path):
        print(f"Error: Markdown file not found at {md_path}")
        return

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Initialize FPDF
    pdf = AgriMatchGuidePDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 20, 15)

    # First Page: Cover Page
    pdf.add_page()
    
    # Elegant Cover Styling
    pdf.set_y(60)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(20, 82, 40) # Deep Forest Green
    pdf.multi_cell(0, 12, "AGRIMATCH", align="C")
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(29, 107, 58) # Medium Green
    pdf.multi_cell(0, 10, "Ghana's Agricultural Intelligence Platform", align="C")
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(122, 144, 136) # Muted Text
    pdf.multi_cell(0, 6, "Web Interface User Guide & Comprehensive Tutorial", align="C")
    
    pdf.set_y(220)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(20, 82, 40)
    pdf.cell(0, 6, "CONFIDENTIAL / FUNDRAISING DECK ATTACHMENT", align="C", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(122, 144, 136)
    pdf.cell(0, 6, "Version 1.0 (June 2026)", align="C", ln=True)
    
    # Process MD Content
    # We will split content by lines
    lines = content.split("\n")
    
    # State tracking
    in_code_block = False
    in_mermaid = False
    code_content = []
    
    # Skip front-matter / Title on first lines since we created a custom cover
    first_title_skipped = False
    
    for line in lines:
        raw_line = line.strip()
        
        # Code block tracking
        if raw_line.startswith("```"):
            if in_code_block:
                # End of code block
                in_code_block = False
                if not in_mermaid:
                    # Render code block
                    pdf.set_font("Courier", "", 8)
                    pdf.set_text_color(50, 50, 50)
                    pdf.set_fill_color(240, 245, 242)
                    code_text = "\n".join(code_content)
                    pdf.multi_cell(0, 4, clean_text(code_text), border=1, fill=True)
                    pdf.ln(4)
                in_mermaid = False
                code_content = []
            else:
                in_code_block = True
                if "mermaid" in raw_line:
                    in_mermaid = True
            continue
            
        if in_code_block:
            if not in_mermaid:
                code_content.append(line)
            continue
            
        # Ignore horizontal rules
        if raw_line == "---":
            continue
            
        # Parse titles
        if raw_line.startswith("# "):
            title_text = raw_line[2:].strip()
            if not first_title_skipped:
                # Skip main title since it matches cover page title
                first_title_skipped = True
                continue
            pdf.add_page() # Start a new page for primary sections
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(20, 82, 40)
            pdf.cell(0, 10, clean_text(title_text), ln=True)
            pdf.ln(4)
            
        elif raw_line.startswith("## "):
            title_text = raw_line[3:].strip()
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(29, 107, 58)
            pdf.cell(0, 8, clean_text(title_text), ln=True)
            pdf.ln(2)
            
        elif raw_line.startswith("### "):
            title_text = raw_line[4:].strip()
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(15, 22, 19)
            pdf.cell(0, 6, clean_text(title_text), ln=True)
            pdf.ln(2)
            
        # Parse images
        elif raw_line.startswith("![") and "]" in raw_line and "(" in raw_line:
            # Extract path
            m = re.search(r'\((.*?)\)', raw_line)
            if m:
                img_path_rel = m.group(1).strip()
                # Resolve path
                if img_path_rel.startswith("images/"):
                    img_path = os.path.join(workspace_dir, "docs", img_path_rel)
                else:
                    img_path = img_path_rel
                
                if os.path.exists(img_path):
                    # Space out
                    pdf.ln(4)
                    # We want to fit the image on the A4 page (width 210mm, margins 15mm left/right, printable width = 180mm)
                    # Fit to width of 150mm and center it
                    # Render image
                    try:
                        pdf.image(img_path, x=30, w=150)
                        pdf.ln(4)
                    except Exception as e:
                        print(f"Failed to embed image {img_path}: {e}")
                else:
                    print(f"Warning: Image file not found: {img_path}")
            
        # Parse bullet lists
        elif raw_line.startswith("- ") or raw_line.startswith("* "):
            bullet_text = line.lstrip("-* ").strip()
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(45, 63, 56)
            
            # Print bullet point symbol
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.cell(5, 5, chr(149)) # bullet point character in standard latin-1
            pdf.set_xy(x + 5, y)
            
            # Print list text
            # We want to bold lead keywords like "*Pitch Detail*" or "**Name**:"
            # Let's check for standard markdown bold pattern e.g. **text** or *text*
            bold_match = re.match(r'^([\*_]{1,2}.*?[\*_]{1,2}):?\s*(.*)', bullet_text)
            if bold_match:
                lead_term = bold_match.group(1).strip("*_")
                rest_text = bold_match.group(2)
                
                pdf.set_font("Helvetica", "B", 10)
                pdf.write(5, clean_text(lead_term + ": "))
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, clean_text(rest_text))
            else:
                pdf.multi_cell(0, 5, clean_text(bullet_text))
            pdf.ln(1)
            
        # Parse numeric lists
        elif re.match(r'^\d+\.\s+', raw_line):
            match = re.match(r'^(\d+)\.\s+(.*)', raw_line)
            num = match.group(1)
            item_text = match.group(2)
            
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(45, 63, 56)
            
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.cell(6, 5, f"{num}.")
            pdf.set_xy(x + 6, y)
            
            bold_match = re.match(r'^([\*_]{1,2}.*?[\*_]{1,2}):?\s*(.*)', item_text)
            if bold_match:
                lead_term = bold_match.group(1).strip("*_")
                rest_text = bold_match.group(2)
                
                pdf.set_font("Helvetica", "B", 10)
                pdf.write(5, clean_text(lead_term + ": "))
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, clean_text(rest_text))
            else:
                pdf.multi_cell(0, 5, clean_text(item_text))
            pdf.ln(1)

        # Standard Paragraphs
        elif raw_line:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(45, 63, 56)
            
            # Parse bold text tags like **text**
            # If there's inline bold, let's write it in chunks.
            # A simple parser:
            parts = re.split(r'(\*\*.*?\*\*)', line)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.write(5, clean_text(part.strip("*")))
                else:
                    pdf.set_font("Helvetica", "", 10)
                    pdf.write(5, clean_text(part))
            pdf.ln(6) # line height + spacing
            
        # Empty line = spacing
        else:
            pdf.ln(2)

    # Save output PDF
    pdf.output(output_pdf_path)
    print(f"Success: PDF generated successfully at {output_pdf_path}")

if __name__ == "__main__":
    build_pdf()
