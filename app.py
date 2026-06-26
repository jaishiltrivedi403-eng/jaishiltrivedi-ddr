#!/usr/bin/env python3
"""
UrbanRoof AI DDR Generator
===========================
Converts site inspection reports + thermal imaging data
into structured, client-ready Detailed Diagnostic Reports (DDR).

Author: [Your Name]
Model:  Claude Sonnet (Anthropic)
"""

import streamlit as st
import anthropic
import PyPDF2
import io
import re
from datetime import datetime

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="UrbanRoof DDR Generator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM STYLING
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
        color: white;
        padding: 28px 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .main-header h1 { margin: 0; font-size: 2rem; }
    .main-header p  { margin: 6px 0 0; opacity: 0.85; }

    .status-box {
        padding: 14px 18px;
        border-radius: 8px;
        margin: 6px 0;
        font-weight: 500;
    }
    .conflict-box { background: #fff3cd; border-left: 5px solid #ffc107; }
    .missing-box  { background: #f8d7da; border-left: 5px solid #dc3545; }
    .ok-box       { background: #d4edda; border-left: 5px solid #28a745; }

    .step-badge {
        display: inline-block;
        background: #e6007a;
        color: white;
        border-radius: 50%;
        width: 26px; height: 26px;
        text-align: center;
        line-height: 26px;
        font-weight: bold;
        margin-right: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes, doc_label: str = "Document") -> str:
    """
    Extract all text from a PDF file.
    Returns a string with page-boundary markers.
    """
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        total_pages = len(reader.pages)
        chunks = [f"[{doc_label} — {total_pages} page(s)]\n"]
        for i, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            if raw.strip():
                chunks.append(f"\n--- Page {i} ---\n{raw}")
        return "\n".join(chunks)
    except Exception as exc:
        return f"[ERROR extracting {doc_label}: {exc}]"


def find_conflicts_and_missing(inspection_text: str, thermal_text: str) -> dict:
    """
    Lightweight heuristic scan for cross-document conflicts
    and obviously missing information fields.
    Returns a dict with 'conflicts' and 'missing' lists.
    """
    insp = inspection_text.lower()
    therm = thermal_text.lower()

    conflicts = []
    missing   = []

    # --- Conflict checks ---
    # Nahani trap: inspection may say Yes while DDR may say No
    if "nahani trap" in insp:
        if "yes" in insp and "no" in insp:
            conflicts.append(
                "Nahani trap status: both 'Yes' and 'No' appear in the inspection report — "
                "inspector should clarify which bathrooms are affected."
            )

    # Leakage timing cross-check
    if "all time" in insp and "monsoon" in insp:
        conflicts.append(
            "Leakage timing: report references both 'All time' and 'Monsoon only' leakage — "
            "these may refer to different areas; treat each area's timing separately."
        )

    # Thermal date vs inspection date
    insp_dates  = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', inspection_text)
    therm_dates = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', thermal_text)
    if insp_dates and therm_dates:
        if insp_dates[0] != therm_dates[0]:
            conflicts.append(
                f"Inspection date ({insp_dates[0]}) and Thermal imaging date "
                f"({therm_dates[0]}) do not match — confirm both are for the same visit."
            )

    # --- Missing information checks ---
    for keyword in ["customer name", "client name", "owner name"]:
        if keyword not in insp:
            missing.append("Customer / Owner Name")
            break

    for keyword in ["property address", "site address", "flat no"]:
        if keyword not in insp:
            missing.append("Full Property Address")
            break

    if "year of construction" not in insp and "age" not in insp:
        missing.append("Property Age / Year of Construction")

    if "not sure" in insp or "paint" not in insp:
        missing.append("Existing External Paint Type & Manufacturer")

    if "structural engineer" not in insp:
        missing.append("Structural Engineer Assessment")

    if "terrace" not in insp and "roof" not in insp:
        missing.append("Terrace / Roof Inspection Data")

    # Deduplicate
    return {
        "conflicts": list(dict.fromkeys(conflicts)),
        "missing":   list(dict.fromkeys(missing)),
    }


def build_system_prompt() -> str:
    return """You are a senior building inspection engineer and report writer at UrbanRoof Private Limited.
You produce accurate, structured, and client-friendly Detailed Diagnostic Reports (DDR).

Your non-negotiable rules:
1. Extract only facts present in the provided documents — NEVER invent or assume.
2. When two documents give conflicting information, explicitly label it:
   CONFLICT: [Document A says X] | [Document B says Y]
3. For any required field with no data, write exactly: Not Available
4. Merge thermal imaging readings with visual observations logically.
5. Use simple, professional English — avoid excessive jargon.
6. Severity levels: HIGH (immediate risk), MODERATE (needed soon), LOW (preventive).
7. Thermal temperature differentials > 5 °C → high moisture; 3–5 °C → moderate; < 3 °C → mild."""


def build_user_prompt(inspection_text: str, thermal_text: str, conflicts: list, missing: list) -> str:
    conflict_block = ""
    if conflicts:
        conflict_block = "\n⚠️  PRE-DETECTED CONFLICTS (must be mentioned in the report):\n"
        conflict_block += "\n".join(f"  • {c}" for c in conflicts)

    missing_block = ""
    if missing:
        missing_block = "\n⚠️  POSSIBLY MISSING INFORMATION (verify in documents; write 'Not Available' if absent):\n"
        missing_block += "\n".join(f"  • {m}" for m in missing)

    today = datetime.now().strftime("%d %B %Y")

    return f"""Generate a complete and professional Detailed Diagnostic Report (DDR) from the two documents below.

════════════════════════════════════════════════
DOCUMENT 1 — SITE INSPECTION REPORT
════════════════════════════════════════════════
{inspection_text[:4500]}

════════════════════════════════════════════════
DOCUMENT 2 — THERMAL IMAGING REPORT
════════════════════════════════════════════════
{thermal_text[:3500]}
{conflict_block}
{missing_block}

════════════════════════════════════════════════
REQUIRED DDR STRUCTURE  (use exactly this format)
════════════════════════════════════════════════

---
# DETAILED DIAGNOSTIC REPORT (DDR)
**Report Prepared By:** UrbanRoof Private Limited  
**Report Date:** {today}  
**Inspection Date:** [from documents, or Not Available]  
**Inspected By:** [from documents, or Not Available]  
**Property Type:** [from documents, or Not Available]  
**Overall Inspection Score:** [from documents, or Not Available]

---

## 1. PROPERTY ISSUE SUMMARY
[3–4 sentences: total impacted areas, primary root causes, urgency level, overall condition]

---

## 2. AREA-WISE OBSERVATIONS

[Create one subsection per impacted area found in the inspection report]

### 2.X  [Area Name]

| Parameter | Details |
|---|---|
| **Symptom (Negative Side)** | [Visible damage — dampness / seepage / staining etc.] |
| **Root Source (Positive Side)** | [Where the water/problem originates] |
| **Thermal Finding** | [Temperature readings from thermal images; if no match found → "Thermal data not specifically mapped to this area"] |
| **Temperature Differential** | [Hotspot − Coldspot in °C; interpret severity] |
| **Thermal Image Reference** | [Image file name from document, or "Not Available"] |

---

## 3. PROBABLE ROOT CAUSE

| Impacted Area | Root Cause | Evidence Source |
|---|---|---|
[One row per area; Evidence Source = "Inspection Report" / "Thermal Image" / "Both"]

**Systemic Root Cause Summary:**  
[1–2 sentences describing the overarching cause across all areas]

---

## 4. SEVERITY ASSESSMENT

| Area | Severity | Priority | Key Reasoning |
|---|---|---|---|
[HIGH / MODERATE / LOW; Priority 1 = most urgent]

---

## 5. RECOMMENDED ACTIONS

### ⚡ Priority 1 — Immediate Actions (0–4 Weeks)
1. [Action with specific method/product if mentioned in documents]

### 🔧 Priority 2 — Secondary Actions (1–3 Months)
1. [Action]

### 🛡️ Priority 3 — Preventive / Long-Term (3–6 Months)
1. [Action]

---

## 6. ADDITIONAL NOTES
- [Important warnings, disclaimers, multi-unit coordination, inspector remarks]

---

## 7. MISSING OR UNCLEAR INFORMATION

| Required Field | Status | Note |
|---|---|---|
| Customer Name | [Available / Not Available] | [value or blank] |
| Property Address | [Available / Not Available] | |
| Property Age | [Available / Not Available] | |
| Paint Type on External Wall | [Available / Not Available] | |
| Structural Engineer Assessment | [Available / Not Available] | |
| Exact Thermal-to-Area Mapping | [Available / Not Available] | |
[Add any other missing fields discovered during analysis]

---
*This DDR is based solely on the provided inspection and thermal imaging documents. No assumptions have been made beyond the available data. — UrbanRoof Private Limited*
---
"""


def generate_ddr(inspection_bytes: bytes, thermal_bytes: bytes, api_key: str) -> tuple[str, dict]:
    """
    Full pipeline:
      1. Extract text from both PDFs
      2. Detect conflicts / missing fields
      3. Call Claude to generate DDR
    Returns (ddr_markdown_text, analysis_dict)
    """
    insp_text  = extract_text_from_pdf(inspection_bytes,  "Inspection Report")
    therm_text = extract_text_from_pdf(thermal_bytes, "Thermal Imaging Report")

    analysis  = find_conflicts_and_missing(insp_text, therm_text)

    client    = anthropic.Anthropic(api_key=api_key)
    response  = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=build_system_prompt(),
        messages=[{
            "role": "user",
            "content": build_user_prompt(insp_text, therm_text,
                                         analysis["conflicts"], analysis["missing"])
        }]
    )

    ddr_text = response.content[0].text
    analysis["inspection_text"] = insp_text
    analysis["thermal_text"]    = therm_text
    return ddr_text, analysis


def ddr_to_html(ddr_markdown: str) -> str:
    """Wrap DDR markdown in a styled HTML page for download."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DDR Report — UrbanRoof</title>
<style>
  body   {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 960px;
            margin: 0 auto; padding: 30px 20px; color: #222; }}
  h1     {{ color: #1a1a2e; border-bottom: 4px solid #e6007a; padding-bottom: 8px; }}
  h2     {{ color: #16213e; border-left: 5px solid #e6007a;
            padding-left: 12px; margin-top: 32px; }}
  h3     {{ color: #0f3460; }}
  table  {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 0.9rem; }}
  th     {{ background: #1a1a2e; color: white; padding: 10px 14px; text-align: left; }}
  td     {{ border: 1px solid #ddd; padding: 8px 14px; }}
  tr:nth-child(even) td {{ background: #f7f7f7; }}
  .header-band {{
    background: linear-gradient(135deg,#1a1a2e,#0f3460);
    color: white; padding: 24px; text-align: center;
    border-radius: 10px; margin-bottom: 28px;
  }}
  .footer {{ text-align: center; color: #666; font-size: 0.8rem;
             margin-top: 40px; border-top: 1px solid #ddd; padding-top: 16px; }}
  code   {{ background:#f4f4f4; padding:2px 6px; border-radius:4px; font-size:0.88rem; }}
  blockquote {{ border-left: 4px solid #e6007a; margin: 0; padding: 10px 18px;
                background: #fff9f0; }}
</style>
</head>
<body>
<div class="header-band">
  <h1 style="margin:0;color:white;border:none;">🏗️ UrbanRoof Private Limited</h1>
  <p style="margin:6px 0 0;opacity:.85;">Detailed Diagnostic Report (DDR) — AI Generated</p>
</div>
<pre style="white-space:pre-wrap;font-family:inherit;line-height:1.7;">
{ddr_markdown}
</pre>
<div class="footer">
  Generated by UrbanRoof AI DDR System · {datetime.now().strftime('%d %B %Y %H:%M')} ·
  Powered by Claude (Anthropic)
</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────

def main():
    # ── Header ────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>🏗️ UrbanRoof — AI DDR Generator</h1>
        <p>Upload your inspection + thermal imaging PDFs → get a professional DDR in seconds</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-api03-...",
            help="Get your key at console.anthropic.com",
        )
        st.markdown("---")
        st.markdown("### 📌 How It Works")
        for step, text in [
            ("1", "Enter your Anthropic API key"),
            ("2", "Upload Inspection Report PDF"),
            ("3", "Upload Thermal Imaging PDF"),
            ("4", "Click **Generate DDR**"),
            ("5", "Review & download the report"),
        ]:
            st.markdown(f'<span class="step-badge">{step}</span>{text}', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🤖 AI System Info")
        st.markdown("""
| Feature | Status |
|---|---|
| Model | Claude Sonnet |
| Conflict Detection | ✅ |
| Missing Info Flag | ✅ |
| Thermal Integration | ✅ |
| Output Formats | MD + HTML |
""")

    # ── File Uploaders ─────────────────────────
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("📋 Inspection Report")
        insp_file = st.file_uploader(
            "Upload Inspection Report PDF",
            type=["pdf"],
            key="insp",
            help="The site inspection form with area observations and checklist",
        )
        if insp_file:
            st.success(f"✅ **{insp_file.name}** ({insp_file.size // 1024} KB)")

    with col2:
        st.subheader("🌡️ Thermal Imaging Report")
        therm_file = st.file_uploader(
            "Upload Thermal Images PDF",
            type=["pdf"],
            key="therm",
            help="PDF with IR thermography images and temperature readings",
        )
        if therm_file:
            st.success(f"✅ **{therm_file.name}** ({therm_file.size // 1024} KB)")

    st.markdown("---")

    # ── Generate Button ────────────────────────
    can_generate = bool(api_key and insp_file and therm_file)
    if not can_generate:
        st.info("⬆️  Please enter your API key and upload both PDFs to enable generation.")

    if st.button(
        "🚀 Generate DDR Report",
        use_container_width=True,
        type="primary",
        disabled=not can_generate,
    ):
        progress = st.progress(0, text="Starting…")

        # Step 1 — Extract
        progress.progress(15, text="📖 Extracting text from Inspection Report…")
        insp_bytes  = insp_file.read()

        progress.progress(30, text="📖 Extracting text from Thermal Report…")
        therm_bytes = therm_file.read()

        # Step 2 — Conflict scan (preview)
        progress.progress(45, text="🔍 Scanning for conflicts and missing information…")
        preview_analysis = find_conflicts_and_missing(
            extract_text_from_pdf(insp_bytes, "Inspection"),
            extract_text_from_pdf(therm_bytes, "Thermal"),
        )
        if preview_analysis["conflicts"]:
            for c in preview_analysis["conflicts"]:
                st.markdown(
                    f'<div class="status-box conflict-box">⚠️ <b>Conflict detected:</b> {c}</div>',
                    unsafe_allow_html=True,
                )
        if preview_analysis["missing"]:
            st.markdown(
                f'<div class="status-box missing-box">ℹ️ '
                f'<b>Potentially missing:</b> {", ".join(preview_analysis["missing"])}</div>',
                unsafe_allow_html=True,
            )

        # Step 3 — Generate DDR
        progress.progress(60, text="🤖 Calling Claude AI to generate DDR…")
        try:
            ddr_text, analysis = generate_ddr(insp_bytes, therm_bytes, api_key)
        except anthropic.AuthenticationError:
            st.error("❌ Invalid API key. Please check and retry.")
            progress.empty()
            return
        except Exception as exc:
            st.error(f"❌ Generation failed: {exc}")
            progress.empty()
            return

        progress.progress(95, text="📄 Formatting report…")

        # Step 4 — Display
        progress.progress(100, text="✅ Done!")
        st.success("✅ DDR Generated Successfully!")

        st.markdown("---")
        st.header("📄 Generated DDR Report")

        tab_report, tab_insp, tab_therm = st.tabs(
            ["📄 DDR Report", "📋 Extracted Inspection Data", "🌡️ Extracted Thermal Data"]
        )

        with tab_report:
            st.markdown(ddr_text)
            st.markdown("---")
            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    label="📥 Download as Markdown",
                    data=ddr_text,
                    file_name=f"DDR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with dl2:
                html_report = ddr_to_html(ddr_text)
                st.download_button(
                    label="📥 Download as HTML",
                    data=html_report,
                    file_name=f"DDR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    use_container_width=True,
                )

        with tab_insp:
            st.text_area("Inspection Report Text", analysis.get("inspection_text", ""), height=450)

        with tab_therm:
            st.text_area("Thermal Report Text", analysis.get("thermal_text", ""), height=450)


if __name__ == "__main__":
    main()
