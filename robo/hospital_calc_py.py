"""Capitulo do CID-10 (mesma regra de js/hospital_calc.js). Uso: agregacao por capitulo, sem dado de pessoa."""
import re

def capitulo_cid(cid):
    c = (cid or "").strip().upper()
    if not re.match(r"^[A-Z]\d{2}", c):
        return None
    L, n = c[0], int(c[1:3])
    if L in "AB": return "I. Doenças infecciosas e parasitárias"
    if L == "C" or (L == "D" and n <= 48): return "II. Neoplasias"
    if L == "D": return "III. Doenças do sangue e imunitárias"
    if L == "E": return "IV. Doenças endócrinas, nutricionais e metabólicas"
    if L == "F": return "V. Transtornos mentais e comportamentais"
    if L == "G": return "VI. Doenças do sistema nervoso"
    if L == "H": return "VII. Doenças do olho e anexos" if n <= 59 else "VIII. Doenças do ouvido"
    if L == "I": return "IX. Doenças do aparelho circulatório"
    if L == "J": return "X. Doenças do aparelho respiratório"
    if L == "K": return "XI. Doenças do aparelho digestivo"
    if L == "L": return "XII. Doenças da pele e do tecido subcutâneo"
    if L == "M": return "XIII. Doenças osteomusculares e do tecido conjuntivo"
    if L == "N": return "XIV. Doenças do aparelho geniturinário"
    if L == "O": return "XV. Gravidez, parto e puerpério"
    if L == "P": return "XVI. Afecções do período perinatal"
    if L == "Q": return "XVII. Malformações congênitas"
    if L == "R": return "XVIII. Sintomas e achados anormais"
    if L in "ST": return "XIX. Lesões, envenenamentos e causas externas"
    if L in "VWXY": return "XX. Causas externas de morbidade e mortalidade"
    if L == "Z": return "XXI. Fatores que influenciam o estado de saúde"
    if L == "U": return "XXII. Códigos para propósitos especiais"
    return None
