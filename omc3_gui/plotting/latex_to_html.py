""" 
Latex to HTML converter
-----------------------

Converts LaTeX commands for Greek letters and other symbols to HTML.
Needed to be able to re-use matplotlib-labels - which understand Latex - 
in pyqtgraph, which does not understand Latex.
"""
from __future__ import annotations

import re

# Dictionary to map Greek LaTeX symbols to HTML
LATEX_TO_HTML_SYMBOLS = {
    # Greek ---
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
    r'\Alpha': 'Α',
    r'\Beta': 'Β',
    r'\Gamma': 'Γ',
    r'\Delta': 'Δ',
    r'\Epsilon': 'Ε',
    r'\Zeta': 'Ζ',
    r'\Eta': 'Η',
    r'\Theta': 'Θ',
    r'\Iota': 'Ι',
    r'\Kappa': 'Κ',
    r'\Lambda': 'Λ',
    r'\Mu': 'Μ',
    r'\Nu': 'Ν',
    r'\Xi': 'Ξ',
    r'\Pi': 'Π',
    r'\Rho': 'Ρ',
    r'\Sigma': 'Σ',
    r'\Tau': 'Τ',
    r'\Upsilon': 'Υ',
    r'\Phi': 'Φ',
    r'\Chi': 'Χ',
    r'\Psi': 'Ψ',
    r'\Omega': 'Ω',
    # Symbols ---
    r'\pm': '&plusmn;',
    r'\times': '&times;',
    r'\Re': '&real;',
    r'\Im': '&image;',
    # Spacing ---
    r'\quad': '&ensp;',
    r'\;': '&thinsp;',
}

def latex_to_html_converter(latex_str: str) -> str:
    """ 
    Converts LaTeX commands for Greek letters and other symbols to HTML.

    Args:
        latex_str (str): LaTeX string to convert.
    
    Returns:
        str: HTML string
    """
    # Convert LaTeX commands for Greek letters to HTML
    html_str = latex_str.replace("$", "")
    for latex, html in LATEX_TO_HTML_SYMBOLS.items():
        html_str = html_str.replace(latex, html)
    
    # Other HTML formatting like superscript/subscript, fractions, etc.
    html_str = re.sub(r'_{([^}]*)}', r'<sub>\1</sub>', html_str)
    html_str = re.sub(r'_(.)', r'<sub>\1</sub>', html_str)
    html_str = re.sub(r'\\frac{([^}]*)}{([^}]*)}', r'<sup>\1</sup>/<sub>\2</sub>', html_str)
    html_str = re.sub(r'\\left\((.*?)\\right\)', r'(\1)', html_str)  # Basic parentheses
    html_str = re.sub(r'\\left\|(.*?)\\right\|', r'|\1|', html_str)  # Absolute values
    
    return html_str
