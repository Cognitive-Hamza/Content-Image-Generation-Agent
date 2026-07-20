# Al-Nafi Image Generation Agent v2.0

Social media post generator & translator for **Al-Nafi International College** and its sub-brands.

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Two Modes

### ✨ Generate New Post
Create fresh social media graphics from scratch. Fill in content, pick visuals, generate with AI.

### 🌐 Translate Existing Post
Upload an existing post image as reference, enter its text content, pick a target language, and the app:
1. Translates all text fields using GPT-4o-mini
2. Shows original vs translated side-by-side (editable)
3. Regenerates the same design in the new language

Supported languages: Urdu, Arabic, Hindi, French, Spanish, German, Turkish, Malay, Bengali, Pashto, Persian, Chinese, Portuguese, Indonesian, Somali, Swahili, English.

---

## App Flow

```
┌─────────────────────┐
│    Landing Page      │
│  ┌───────┐ ┌──────┐ │
│  │Generate│ │Trans-│ │
│  │  New   │ │late  │ │
│  └───┬───┘ └──┬───┘ │
└──────┼────────┼──────┘
       ↓        ↓
  Generation  Translation
    Page        Page
```

Both pages share the same layout: 65% left workspace + 35% right controls panel.

---

## Supported Providers

| Provider | Model | Quality Tiers |
|---|---|---|
| **OpenAI GPT-Image-2** (default) | `gpt-image-2` | low / medium / high |
| **OpenAI GPT-Image-1** | `gpt-image-1` | low / medium / high |
| **Google Gemini Imagen 3** | `imagen-3.0-generate-002` | — |
| **Nano Banana** | placeholder | — |
| **Prompt Only** | no API needed | JSON output |

---

## Deploy on Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → set `app.py` as main file → Deploy

API keys are entered at runtime per-session (never stored).
