# Police Hébreu pour PDFs IGV

## Installation requise

Pour afficher correctement le texte hébreu dans les PDFs Mini-Analyse, téléchargez la police **Noto Sans Hebrew** :

### 1. Télécharger la police
- URL: https://fonts.google.com/noto/specimen/Noto+Sans+Hebrew
- Cliquer sur "Download family"
- Extraire le fichier ZIP

### 2. Installer dans le backend
Copier le fichier `NotoSansHebrew-Regular.ttf` dans ce dossier :
```
backend/fonts/NotoSansHebrew-Regular.ttf
```

### 3. Alternative (si Noto Sans Hebrew indisponible)
Vous pouvez utiliser d'autres polices Unicode hébraïques :
- **David CLM** (libre)
- **Heebo** (Google Fonts)
- **Frank Ruehl CLM** (libre)

Le fichier doit être nommé exactement `NotoSansHebrew-Regular.ttf` ou modifier [mini_analysis_routes.py](../mini_analysis_routes.py#L22-L35) pour pointer vers le bon nom de fichier.

## Licence
Noto Sans Hebrew est sous licence **OFL (Open Font License)** - libre d'utilisation commerciale.

## Vérification
Après installation, redémarrer le backend et générer un PDF en hébreu pour vérifier que le texte s'affiche correctement (pas de carrés □).

## Note technique
La police est enregistrée au démarrage du backend via:
```python
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

pdfmetrics.registerFont(TTFont('HebrewFont', hebrew_font_path))
```

Les paragraphes hébreu utilisent:
- `fontName='HebrewFont'`
- `alignment=TA_RIGHT` (RTL)
- `wordWrap='RTL'`
