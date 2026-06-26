# 🏗️ UrbanRoof AI DDR Generator

An AI-powered system that converts raw site inspection data + thermal imaging reports
into structured, client-ready **Detailed Diagnostic Reports (DDR)**.

---

## 🧠 What It Does

| Step | Action |
|------|--------|
| 1 | Accepts two PDF inputs: Site Inspection Report + Thermal Imaging Report |
| 2 | Extracts all text from both PDFs automatically |
| 3 | Detects conflicts and missing information between documents |
| 4 | Calls Claude AI (Anthropic) to reason over the combined data |
| 5 | Generates a fully structured DDR with 7 sections |
| 6 | Outputs downloadable Markdown + HTML report |

---

## 📁 Project Structure

```
ddr_generator/
├── app.py               ← Main Streamlit application (run this)
├── requirements.txt     ← Python dependencies
├── README.md            ← This file
└── sample_output/
    └── DDR_Sample.html  ← Example DDR output from sample documents
```

---

## ⚙️ Setup — Local (Jupyter / Terminal)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get an Anthropic API key
- Go to https://console.anthropic.com
- Create an account → API Keys → Create Key
- Copy the key (starts with `sk-ant-...`)

### 3. Run the Streamlit app
```bash
streamlit run app.py
```

The app will open at **http://localhost:8501**

---

## ☁️ Deploy for Free Live Link (Streamlit Cloud)

1. Push this folder to a **GitHub repository** (public or private)
2. Go to **https://share.streamlit.io**
3. Sign in with GitHub
4. Click **"New app"** → Select your repo → set `app.py` as the main file
5. Click **Deploy** → You get a live URL like:
   `https://your-username-ddr-generator.streamlit.app`
6. Use this URL as your **submission live link**

> **Tip:** Store your Anthropic API key in Streamlit Cloud Secrets:
> In the app settings → Secrets → add:
> ```
> ANTHROPIC_API_KEY = "sk-ant-..."
> ```
> Then in `app.py`, replace `api_key = st.text_input(...)` with:
> ```python
> api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
> ```

---

## 📓 Jupyter Notebook (Alternative)

If you prefer Jupyter/Colab, open `DDR_Generator_Notebook.ipynb`.

To run on **Google Colab** (free shareable link):
1. Upload the `.ipynb` to Google Drive
2. Open with Colab
3. Share → "Anyone with the link can view"
4. Use that Colab link as your live link

---

## 📤 Submission Checklist

- [ ] GitHub repo with `app.py` + `requirements.txt`
- [ ] Live Streamlit link (or Colab link)
- [ ] Loom video (3–5 min) explaining the system
- [ ] Google Drive folder with all files + screenshots

---

## 🏗️ System Architecture

```
[ PDF 1: Inspection Report ]  ──┐
                                 ├──► Text Extraction (PyPDF2)
[ PDF 2: Thermal Images PDF ]  ──┘        │
                                          ▼
                              Conflict & Missing Info Detection
                                          │
                                          ▼
                              Claude AI (claude-sonnet-4-6)
                              ┌─────────────────────────────┐
                              │  System Prompt: Expert DDR  │
                              │  User Prompt: Both doc texts │
                              │  + Detected conflicts        │
                              └─────────────────────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────────┐
                              │     Generated DDR Report    │
                              │  1. Property Issue Summary  │
                              │  2. Area-wise Observations  │
                              │  3. Root Cause              │
                              │  4. Severity Assessment     │
                              │  5. Recommended Actions     │
                              │  6. Additional Notes        │
                              │  7. Missing Info            │
                              └─────────────────────────────┘
                                          │
                              ┌───────────┴────────────┐
                              ▼                        ▼
                        Markdown (.md)           HTML (.html)
                         Download                 Download
```

---

## 🔍 Key Design Decisions

**Why Claude AI?**
- Superior at structured reasoning over multi-source documents
- Excellent instruction-following (strict formatting compliance)
- Handles ambiguous / conflicting data better than GPT models in tests

**Why Streamlit?**
- Zero-config web UI in pure Python
- Free live hosting on streamlit.io
- Familiar to data scientists and engineers

**Why PyPDF2?**
- Lightweight, no external dependencies
- Works on any PDF text layer
- Fast enough for inspection-sized documents

---

## ⚠️ Limitations

1. **Images not extracted** — PyPDF2 can only extract text. Thermal camera images embedded in the PDF are not included in the AI prompt. Solution: use `pdf2image` + `base64` encoding + Claude vision API (planned improvement).
2. **Thermal-to-area mapping** — The thermal PDF doesn't label which image belongs to which room. The AI notes this as "Not Available" for precise mapping.
3. **Long PDFs** — Very long PDFs are truncated at ~4500 tokens for the inspection text. Solution: chunked summarization (planned improvement).

---

## 🚀 Planned Improvements

- [ ] Extract and embed thermal images via Claude Vision API
- [ ] Auto-detect property address from OCR
- [ ] Export as formatted Word (.docx) report
- [ ] Multi-property batch processing
- [ ] Confidence scoring for each finding
