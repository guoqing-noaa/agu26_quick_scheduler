# AGU Quick Scheduler

<p align="center">
  <img src="logo.jpg" alt="AGU Quick Scheduler Logo" width="300" style="border-radius: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
</p>

A fast, offline-ready personal schedule builder for the **AGU 2026 Annual Meeting** (American Geophysical Union, San Francisco, CA, December 7–11, 2026).

## ✨ Features

- **⚡ Fast & Responsive**: Instant full-text search across all 25,000+ presentation titles, abstracts, authors, and rooms.
- **🌐 Science Sections**: Structured top-level navigation by AGU Science Sections (Atmospheric Sciences, Biogeosciences, Hydrology, Ocean Sciences, Planetary Sciences, Cryosphere, etc.) and Town Halls/Events.
- **🔒 Local Storage**: Your schedule is saved in your browser's local storage and can be backed up as a `my_schedule.json` file.
- **🔗 Add by Link**: Paste any AGU presentation or session URL / ID (e.g., `Paper/2062517` or `Session/285035` or `https://studio.m-anage.com/agu/agu26/meetingapp.cgi/Paper/2062517`) and the app retrieves the latest information directly from the meeting system.
- **📅 Multiple Export Options**: Export your custom schedule to HTML, PDF, JSON, ICS calendar (Apple/Google/Outlook), or AI prompts.
- **📱 Mobile-Friendly**: Fully responsive interface optimized for smartphones, tablets, and laptops.

## 🚀 Usage

### 1. Launch the App
In this folder, run:
```bash
python3 app.py
```
This automatically starts a lightweight local server and opens `http://localhost:8081/` in your default browser.

### 2. Updating Data in the Final Days

If speakers withdraw or room numbers change right before the meeting, simply run:
```bash
python3 fetch_agu_program.py --meeting agu26
```
- Fetches the fresh dataset from the AGU Confex / m-anage API.
- Your custom schedule **remains completely intact** because it references stable presentation and session IDs.
- Any withdrawn talks or room changes will display warning indicators in your schedule view.

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

## ⚠️ Disclaimer

This is an independent, open-source community tool and does not replace the official AGU meeting app. Please always verify official room assignments and schedule details on the AGU site.
