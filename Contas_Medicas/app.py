import fitz

def ver_texto_bruto(caminho_pdf, pagina=0):
    doc = fitz.open(caminho_pdf)
    texto = doc[pagina].get_text()
    # Mostrar primeiras 3000 chars da página 1
    print(repr(texto[:3000]))

ver_texto_bruto("Colesterol_Total.pdf", 0)