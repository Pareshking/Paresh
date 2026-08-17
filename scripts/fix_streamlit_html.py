from pathlib import Path

p = Path("src/ui/theme.py")
text = p.read_text()
text = text.replace("import streamlit.components.v1 as components\n", "")
text = text.replace("components.html(", "st.iframe(")
text = text.replace(", scrolling=True)", ")")
text = text.replace("Rendered via components.html", "Rendered via st.iframe")
p.write_text(text)
