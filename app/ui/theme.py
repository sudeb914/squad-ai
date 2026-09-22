"""Dark-purple theme (QSS) matching the simple single-window Squad AI design."""

COLORS = {
    "bg": "#0a0713", "card": "#170f2b", "card2": "#1d1436", "border": "#2a2050",
    "text": "#ece9ff", "muted": "#9990c4", "primary": "#a855f7",
    "primary2": "#7c3aed", "accent": "#c084fc", "success": "#34d399",
    "danger": "#fb7185", "user": "#6d28d9", "ai": "#17122b",
}

QSS = f"""
QWidget {{
    background: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}}
#topbar {{ border-bottom: 1px solid {COLORS['border']}; }}
#brand {{
    background: {COLORS['card2']};
    border: 1px solid {COLORS['border']};
    border-radius: 999px;
    font-weight: 800; font-size: 13px;
    padding: 6px 16px;
}}
QPushButton#icon {{
    background: rgba(255,255,255,0.03);
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    font-size: 15px;
    min-width: 34px; min-height: 34px; max-width: 34px; max-height: 34px;
}}
QPushButton#icon:hover {{ border-color: {COLORS['primary']}; }}
QPushButton#icon:checked {{
    border-color: {COLORS['primary']};
    background: {COLORS['card2']};
}}

QScrollArea, #chatInner {{ border: none; background: {COLORS['bg']}; }}

#emptyTitle {{ font-size: 17px; font-weight: 800; color: {COLORS['text']}; }}
#emptySub {{ color: {COLORS['muted']}; font-size: 12px; }}

#userBubble {{
    background: {COLORS['user']};
    border-radius: 14px; border-bottom-right-radius: 5px;
    padding: 10px 12px; font-size: 13px;
}}
#aiBubble {{
    background: {COLORS['ai']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px; border-bottom-left-radius: 5px;
    padding: 10px 12px; font-size: 13px;
}}
#avatar {{
    background: {COLORS['primary2']};
    border-radius: 13px; min-width: 26px; max-width: 26px;
    min-height: 26px; max-height: 26px;
}}
#meta {{ color: {COLORS['muted']}; font-size: 11px; }}

#composer {{ border-top: 1px solid {COLORS['border']}; background: {COLORS['bg']}; }}
QLineEdit#chatInput {{
    background: {COLORS['card2']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px; padding: 11px 12px; font-size: 13px;
}}
QLineEdit#chatInput:focus {{ border-color: {COLORS['primary2']}; }}

QPushButton#cbtn {{
    background: rgba(255,255,255,0.04);
    border: 1px solid {COLORS['border']};
    border-radius: 12px; font-size: 16px;
    min-width: 42px; min-height: 42px; max-width: 42px; max-height: 42px;
}}
QPushButton#cbtn:hover {{ border-color: {COLORS['primary']}; }}
QPushButton#send {{
    background: {COLORS['primary']}; border: none; color: #fff;
}}
QPushButton#send:hover {{ background: {COLORS['primary2']}; }}

QPushButton#chip {{
    background: rgba(255,255,255,0.03);
    border: 1px solid {COLORS['border']};
    border-radius: 999px; padding: 5px 12px; color: {COLORS['muted']};
    font-size: 12px; font-weight: 600;
}}
QPushButton#chip:checked {{
    color: #fff; border-color: {COLORS['primary']};
    background: {COLORS['card2']};
}}

/* Settings / Help panels */
QLabel#sectionTitle {{ font-size: 13px; font-weight: 800; color: #d8d1f7; }}
QLabel#fieldLabel {{ font-size: 12px; font-weight: 700; color: #cfc7f5; }}
QLabel#hint {{ color: {COLORS['muted']}; font-size: 11px; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background: {COLORS['card2']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px; padding: 9px; font-size: 13px; color: {COLORS['text']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {COLORS['primary2']};
}}
QPushButton#primary {{
    background: {COLORS['primary']}; border: none; color: #fff;
    border-radius: 12px; padding: 11px; font-weight: 800; font-size: 13px;
}}
QPushButton#primary:hover {{ background: {COLORS['primary2']}; }}
QPushButton#danger {{
    background: {COLORS['danger']}; border: none; color: #fff;
    border-radius: 12px; padding: 11px; font-weight: 800;
}}
QPushButton#ghost {{
    background: rgba(255,255,255,0.04); color: #d8d1f7;
    border: 1px solid {COLORS['border']}; border-radius: 12px; padding: 10px;
    font-weight: 700;
}}
QPushButton#ghost:hover {{ border-color: {COLORS['primary']}; }}
QPushButton#mini {{
    background: rgba(255,255,255,0.04); color: #d8d1f7;
    border: 1px solid {COLORS['border']}; border-radius: 8px;
    padding: 5px 11px; font-size: 12px; font-weight: 600;
}}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
