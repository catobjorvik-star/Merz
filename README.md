<p align="center">
  <img src="frontend/public/merz-logo.svg" width="220" />
</p>

<h1 align="center">PDF-EXCEL IMPORT</h1>

<p align="center">
  Schreinerei MERZ – Fensterimport Tool<br>
  Developed by CBjorvik
</p>

---

## Overview

This application automates the transfer of window data from architect PDFs into the MERZ Excel calculation template.

It replaces a manual workflow with a fast, reliable, and repeatable system.

---

## Key Features

### PDF → Structured Data
- Supports:
  - window tables
  - architectural window plans
- Extracts:
  - ID (F-1.6, etc.)
  - dimensions (RBM)
  - quantity
  - window type
  - opening direction (DIN rechts / links)

---

### Smart Description Generation

Example output:

```text
1,13×2,57 | Dreh-Kippflügel | DIN rechts, DIN links
```

---

### Supplier Price Integration
- Uses internal supplier price list (PDF)
- Applies:
  - dimension correction (-30 mm rule)
- Returns:
  - price (€)
  - glass area index (m²)
  - match confidence

---

### Excel Integration
- Writes only into input columns (I–M)
- Keeps formulas intact
- Automatically extends table
- Footer + calculations remain working

---

### Built-in MERZ Template
- No need to upload Excel template
- Always uses correct version

---

## Tech Stack

Frontend:
- React (Vite)

Backend:
- FastAPI
- pdfplumber / PyPDF
- openpyxl

Deployment:
- Docker
- Render

---

## Usage

1. Upload PDF
2. Click **Vorschau laden**
3. Click **Excel erzeugen**
4. Download finished file

---

## Mobile Support

- Auto-optimized for phones
- Clean layout
- Easy tap controls

---

## Branding

MERZ colors:
- Red: `#E30613`
- Dark: `#1E1E1E`
- Light: `#F5F5F5`

---

## Notes

- Built for real MERZ workflow
- Focus on reliability and simplicity
- Not a generic tool

---

## Author

Developed by **CBjorvik**
