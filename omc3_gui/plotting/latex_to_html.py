import re

# Dictionary to map Greek LaTeX symbols to HTML
LATEX_TO_HTML_SYMBOLS = {
    r'\alpha': 'α',
    r'\beta': 'β',
    r'\gamma': 'γ',
    r'\delta': 'δ',
    r'\epsilon': 'ε',
    r'\zeta': 'ζ',
    r'\eta': 'η',
    r'\theta': 'θ',
    r'\iota': 'ι',
    r'\kappa': 'κ',
    r'\lambda': 'λ',
    r'\mu': 'μ',
    r'\nu': 'ν',
    r'\xi': 'ξ',
    r'\pi': 'π',
    r'\rho': 'ρ',
    r'\sigma': 'σ',
    r'\tau': 'τ',
    r'\upsilon': 'υ',
    r'\phi': 'φ',
    r'\chi': 'χ',
    r'\psi': 'ψ',
    r'\omega': 'ω',
    r'\quad': '&ensp;',
    # You can add more Greek letters as needed
}

def latex_to_html_converter(latex_str):
    # Convert LaTeX commands for Greek letters to HTML
    latex_str = latex_str.replace("$", "")
    for latex, html in LATEX_TO_HTML_SYMBOLS.items():
        latex_str = latex_str.replace(latex, html)
    
    # Other HTML formatting like superscript/subscript, fractions, etc.
    latex_str = re.sub(r'_{([^}]*)}', r'<sub>\1</sub>', latex_str)
    latex_str = re.sub(r'_(.)', r'<sub>\1</sub>', latex_str)
    latex_str = re.sub(r'\\frac{([^}]*)}{([^}]*)}', r'<sup>\1</sup>/<sub>\2</sub>', latex_str)
    latex_str = re.sub(r'\\left\((.*?)\\right\)', r'(\1)', latex_str)  # Basic parentheses
    
    return latex_str
