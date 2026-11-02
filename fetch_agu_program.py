#!/usr/bin/env python3
"""
fetch_agu_program.py

Pulls complete program data from AGU Confex / m-anage API:
(Sections/Programs, Sessions, Papers/Abstracts, SlotData/Rooms/Times)
and compiles into a clean, normalized agu_program.json for the AGU Quick Scheduler.
"""

import argparse
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from datetime import datetime

# AGU Science & Interdisciplinary Topic Rules for Pre-computed Tags
TOPIC_RULES = {
    "MachineLearning_AI": [
        r"\bmachine learning\b", r"\bdeep learning\b", r"\bneural network\b",
        r"\bartificial intelligence\b", r"\bsurrogate\b", r"\bgraph neural\b",
        r"\bfoundation model\b", r"\btransformer\b", r"\bgenerative\b",
        r"\bphysics-informed\b", r"\bpiml\b", r"\bdiffusion model\b", r"\blarge language model\b"
    ],
    "DataAssimilation": [
        r"\bdata assimilation\b", r"\bradar assimilation\b", r"\bsatellite assimilation\b",
        r"\benkf\b", r"\bensemble kalman\b", r"\bvariational\b", r"\b3dvar\b", r"\b4dvar\b",
        r"\bjedi\b", r"\bkalman filter\b", r"\bbackground error\b", r"\bstate estimation\b"
    ],
    "Atmospheric_NWP": [
        r"\bnumerical weather prediction\b", r"\bnwp\b", r"\batmospheric dynamics\b",
        r"\baerosol\b", r"\bcloud microphysics\b", r"\bconvection\b", r"\bprecipitation\b",
        r"\brrfs\b", r"\bufs\b", r"\bwrf\b", r"\bgfs\b", r"\bboundary layer\b",
        r"\btroposphere\b", r"\bstratosphere\b", r"\bmonsoon\b"
    ],
    "Hydrology_Water": [
        r"\bhydrolog\w+", r"\bstreamflow\b", r"\bgroundwater\b", r"\bwatershed\b",
        r"\brunoff\b", r"\bflood\w*", r"\bdrought\b", r"\bsoil moisture\b",
        r"\bevaporation\b", r"\bevapotranspiration\b", r"\baquifer\b", r"\bwater quality\b"
    ],
    "Ocean_Cryosphere": [
        r"\bocean circulation\b", r"\bsea ice\b", r"\bice sheet\b", r"\bglacier\b",
        r"\bsea level\b", r"\bcoastal\b", r"\bmarine\b", r"\bpermafrost\b",
        r"\bantarctic\b", r"\barctic\b", r"\bocean acidification\b", r"\bupwelling\b"
    ],
    "SolidEarth_Geophysics": [
        r"\bearthquake\b", r"\bseism\w+", r"\bfault\b", r"\bsubduction\b",
        r"\bplate tectonics\b", r"\bvolcan\w+", r"\bmagma\b", r"\bmantle\b",
        r"\blithosphere\b", r"\bcrust\b", r"\bgeodynam\w+", r"\bgeodesy\b"
    ],
    "SpacePhysics_Planetary": [
        r"\bspace weather\b", r"\bmagnetosphere\b", r"\bionosphere\b", r"\baurora\b",
        r"\bsolar wind\b", r"\bheliosphere\b", r"\bplanetary\b", r"\bmars\b",
        r"\bmoon\b", r"\blunar\b", r"\bexoplanet\b", r"\bcoronal mass ejection\b"
    ],
    "Biogeosciences_Carbon": [
        r"\bcarbon cycle\b", r"\becosystem\b", r"\bgreenhouse gas\b", r"\bmethane\b",
        r"\bco2\b", r"\bflux\b", r"\bphotosynthesis\b", r"\bsoil organic\b",
        r"\bforest\b", r"\bvegetation\b", r"\bbiogeochem\w+", r"\bprimary production\b"
    ],
    "Radar_RemoteSensing": [
        r"\bremote sensing\b", r"\bsatellite\b", r"\bradar\b", r"\bsar\b",
        r"\binsar\b", r"\blidar\b", r"\bradiometer\b", r"\blandsat\b",
        r"\bsentinel\b", r"\breflectance\b", r"\bswot\b", r"\bgnss\b"
    ],
    "NaturalHazards_Risk": [
        r"\bnatural hazard\w*", r"\bwildfire\b", r"\btsunami\b", r"\blandslide\b",
        r"\bextreme event\b", r"\brisks?\b", r"\bvulnerability\b", r"\bdisaster\b",
        r"\bearly warning\b", r"\bresilience\b"
    ]
}

def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<(?:br|p|/p|div|/div)[^>]*>", " ", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def extract_primary_presenter(top_display_html: str, default_presenter: str = "") -> str:
    """Extract primary presenter from <b> tag or fallback."""
    if not top_display_html:
        return default_presenter or ""
    m = re.search(r"<b>(.*?)</b>", top_display_html, re.IGNORECASE)
    if m:
        return clean_html(m.group(1))
    return default_presenter or clean_html(top_display_html.split(",")[0])

def tag_content(title: str, abstract: str) -> list:
    """Assign precomputed topic tags based on regex patterns in title and abstract."""
    combined = f"{title} {abstract}".lower()
    tags = []
    for topic, patterns in TOPIC_RULES.items():
        for pat in patterns:
            if re.search(pat, combined, re.IGNORECASE):
                tags.append(topic)
                break
    return tags

def fetch_agu_endpoint(meeting_code: str, endpoint: str, ctx=None):
    """Fetch raw JSON from AGU studio.m-anage.com meetingapi.cgi."""
    if ctx is None:
        ctx = ssl._create_unverified_context()
    
    url = f"https://studio.m-anage.com/agu/{meeting_code}/meetingapi.cgi/{endpoint}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content)

def build_program_dataset(meeting_code="agu26", output_path="agu_program.json"):
    print(f"=== Fetching AGU Program Data for [{meeting_code}] ===")
    ctx = ssl._create_unverified_context()
    
    t0 = time.time()
    
    print("1/5 Fetching Sections & Programs (Program)...")
    raw_programs = fetch_agu_endpoint(meeting_code, "Program", ctx)
    print(f"    Loaded {len(raw_programs)} programs in {time.time() - t0:.1f}s")
    
    t1 = time.time()
    print("2/5 Fetching Program Book navigation (ModuleProgramBook)...")
    raw_book = fetch_agu_endpoint(meeting_code, "ModuleProgramBook", ctx)
    valid_section_urls = set()
    if raw_book and isinstance(raw_book, list) and len(raw_book) > 0:
        valid_section_urls = set(raw_book[0].get("ChildList_Program", []))
    print(f"    Identified {len(valid_section_urls)} primary science sections in book.")

    t2 = time.time()
    print("3/5 Fetching all Sessions...")
    raw_sessions = fetch_agu_endpoint(meeting_code, "Session", ctx)
    print(f"    Loaded {len(raw_sessions)} sessions in {time.time() - t2:.1f}s")

    t3 = time.time()
    print("4/5 Fetching Slot & Room locations (SlotData)...")
    raw_slots = fetch_agu_endpoint(meeting_code, "SlotData", ctx)
    print(f"    Loaded {len(raw_slots)} slot records in {time.time() - t3:.1f}s")

    t4 = time.time()
    print("5/5 Fetching all Presentations & Abstracts (Paper)...")
    raw_papers = fetch_agu_endpoint(meeting_code, "Paper", ctx)
    print(f"    Loaded {len(raw_papers)} papers in {time.time() - t4:.1f}s")

    print("\nProcessing and normalizing data...")

    # Build Slot Lookup: Paper/ID -> room & times; Session/ID -> room & times
    paper_slot_map = {}
    session_slot_map = {}

    for slot in raw_slots:
        entry_id = slot.get("Entryid")
        sess_id = slot.get("Session_id")
        room = clean_html(slot.get("Room_Name", ""))
        date = slot.get("Slot_Date", "")
        start_time = slot.get("Slot_StartTime", "")
        end_time = slot.get("Slot_EndTime", "")
        sess_start = slot.get("Slot_SessionStartTime", "")
        sess_end = slot.get("Slot_SessionEndTime", "")
        venue = clean_html(slot.get("Property_Name", "") or "Moscone Center")
        presenter = clean_html(slot.get("Entry_Presenters", ""))

        slot_info = {
            "room": room,
            "venue": venue,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "session_start": sess_start,
            "session_end": sess_end,
            "presenter": presenter
        }

        if entry_id:
            paper_slot_map[entry_id] = slot_info
        if sess_id:
            session_slot_map[sess_id] = slot_info

    # 1. Normalize Sections / Programs
    sections = []
    sec_by_id = {}
    
    # Exclude system reservation pools or test sections
    EXCLUDED_CODES = {
        "TEST", "PODS", "LOUNGE", "MTGRM", "SECTIONLOUNGE", "PIO",
        "GENERAL", "KEYPLENARY", "TRASH", "WASTE BASKET"
    }

    for p in raw_programs:
        p_url = p.get("_url", "")
        p_id = p.get("id", "")
        title = clean_html(p.get("Title", ""))
        code = p.get("ProgramCode", "").strip()
        
        if code.upper() in EXCLUDED_CODES or "TEST" in title.upper():
            continue
            
        session_ids = [s.replace("Session/", "") for s in p.get("ChildList_Session", [])]
        paper_ids = [pap.replace("Paper/", "") for pap in p.get("ChildList_Paper", [])]
        
        # Must have at least one session or paper
        if not session_ids and not paper_ids:
            continue

        is_science_sec = (p_url in valid_section_urls or f"Program/{p_id}" in valid_section_urls)

        s_data = {
            "id": p_id,
            "code": code,
            "title": title,
            "nav_title": clean_html(p.get("NavBarTitle", "") or title),
            "is_science_section": is_science_sec,
            "session_ids": session_ids,
            "paper_ids": paper_ids
        }
        sections.append(s_data)
        sec_by_id[p_id] = s_data

    # Sort sections: primary science sections first (alphabetically), then special events/townhalls
    sections.sort(key=lambda s: (0 if s["is_science_section"] else 1, s["title"]))

    # 2. Normalize Sessions
    sessions = {}
    for s in raw_sessions:
        s_id = s.get("id", "")
        if not s_id:
            continue
        
        title = clean_html(s.get("Title", ""))
        p_code = s.get("ProgramCode", "")
        p_title = clean_html(s.get("ProgramTitle", ""))
        
        # Extract section id from ParentList_ParentEntries
        parents = s.get("ParentList_ParentEntries", [])
        sec_id = ""
        for parent in parents:
            if parent.startswith("Program/"):
                sec_id = parent.replace("Program/", "")
                break
        
        # Room & Slot info
        slot_info = session_slot_map.get(s_id, {})
        sort_time = s.get("SortableTimeString", "") # format: 2026-12-08_16:15:00_17:45:00
        date = slot_info.get("date", "")
        start_time = slot_info.get("start_time", "") or slot_info.get("session_start", "")
        end_time = slot_info.get("end_time", "") or slot_info.get("session_end", "")

        if not date and sort_time:
            parts = sort_time.split("_")
            if len(parts) >= 1:
                date = parts[0]
            if len(parts) >= 2 and not start_time:
                start_time = parts[1]
            if len(parts) >= 3 and not end_time:
                end_time = parts[2]

        cochairs = clean_html(s.get("TopDisplay", ""))
        if "Cochairs:" in cochairs:
            cochairs = cochairs.replace("Cochairs:", "").strip()

        paper_ids = [p.replace("Paper/", "") for p in s.get("ChildList_Paper", [])]

        session_num = s.get("FinalSessionNumber", "") or s.get("FinalNumber", "")

        sessions[s_id] = {
            "id": s_id,
            "title": title,
            "session_number": session_num,
            "section_id": sec_id,
            "section_code": p_code,
            "section_title": p_title,
            # alias conference keys for full drop-in compatibility
            "conference_id": sec_id,
            "conference_code": p_code,
            "conference_title": p_title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "room": slot_info.get("room", ""),
            "venue": slot_info.get("venue", "Moscone Center"),
            "cochairs": cochairs,
            "good_type": s.get("Session_GoodType", "") or s.get("GoodType", "Session"),
            "paper_ids": paper_ids,
            "withdrawn": bool(s.get("Withdrawn", ""))
        }

    # 3. Normalize Papers
    papers = {}
    for p in raw_papers:
        p_id = p.get("id", "")
        if not p_id:
            continue
        
        title = clean_html(p.get("Title", ""))
        abstract = clean_html(p.get("Abstract", ""))
        paper_num = p.get("FinalPaperNumber", "") or p.get("FinalNumber", "")
        good_type = p.get("Session_GoodType", "") or p.get("GoodType", "Oral")
        raw_top_display = p.get("TopDisplay", "")
        authors = clean_html(raw_top_display)
        withdrawn = bool(p.get("Withdrawn", "") or p.get("WithdrawnFromTechprogram", "0") == "1")

        # Session & Section linkage
        parents = p.get("ParentList_ParentEntries", [])
        sess_id = ""
        sec_id = ""
        for parent in parents:
            if parent.startswith("Session/"):
                sess_id = parent.replace("Session/", "")
            elif parent.startswith("Program/"):
                sec_id = parent.replace("Program/", "")

        # Fallback section from parent session if needed
        if not sec_id and sess_id and sess_id in sessions:
            sec_id = sessions[sess_id].get("section_id", "")

        # Slot info
        slot_info = paper_slot_map.get(f"Paper/{p_id}", {})
        sort_time = p.get("SortableTimeString", "") # format: 2026-12-08_17:30:00_17:45:00
        date = slot_info.get("date", "")
        start_time = slot_info.get("start_time", "")
        end_time = slot_info.get("end_time", "")
        room = slot_info.get("room", "")

        if not date and sort_time:
            parts = sort_time.split("_")
            if len(parts) >= 1:
                date = parts[0]
            if len(parts) >= 2 and not start_time:
                start_time = parts[1]
            if len(parts) >= 3 and not end_time:
                end_time = parts[2]

        # Inherit room/date from session if missing on paper
        if sess_id and sess_id in sessions:
            parent_sess = sessions[sess_id]
            if not room:
                room = parent_sess.get("room", "")
            if not date:
                date = parent_sess.get("date", "")
            if not start_time and parent_sess.get("start_time"):
                start_time = parent_sess.get("start_time")
                end_time = parent_sess.get("end_time")

        # Presenter
        presenter = slot_info.get("presenter") or extract_primary_presenter(raw_top_display)

        # Precomputed tags
        tags = tag_content(title, abstract)

        papers[p_id] = {
            "id": p_id,
            "title": title,
            "number": paper_num,
            "session_id": sess_id,
            "section_id": sec_id,
            "conference_id": sec_id,  # alias for drop-in compatibility
            "type": good_type,
            "presenter": presenter,
            "authors": authors,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "room": room,
            "abstract": abstract,
            "tags": tags,
            "withdrawn": withdrawn
        }

    # Ensure section['paper_ids'] contains all papers belonging to the section
    sec_paper_map = {s["id"]: set() for s in sections}
    for pid, p in papers.items():
        sid = p.get("section_id")
        if sid in sec_paper_map:
            sec_paper_map[sid].add(pid)
    for s in sections:
        combined = set(s.get("paper_ids", [])) | sec_paper_map.get(s["id"], set())
        s["paper_ids"] = list(combined)

    dataset = {
        "metadata": {
            "meeting_code": meeting_code,
            "meeting_title": f"AGU26 Annual Meeting",
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "total_sections": len(sections),
            "total_conferences": len(sections),  # alias
            "total_sessions": len(sessions),
            "total_papers": len(papers),
            "available_tags": list(TOPIC_RULES.keys())
        },
        "sections": sections,
        "conferences": sections,  # alias for backward/drop-in compatibility
        "sessions": sessions,
        "papers": papers
    }

    print(f"\nWriting dataset to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Done! Saved {file_size_mb:.2f} MB JSON dataset in {time.time() - t0:.1f}s total.")
    print(f"Summary:")
    print(f"  • Science Sections & Programs: {len(sections)}")
    print(f"  • Sessions:                     {len(sessions)}")
    print(f"  • Papers/Presentations:        {len(papers)}")
    print(f"  • Pre-computed Tags:           {len(TOPIC_RULES)}")

    return dataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and normalize AGU Confex / m-anage program dataset.")
    parser.add_argument("--meeting", default="agu26", help="AGU meeting code (default: agu26)")
    parser.add_argument("--output", default="agu_program.json", help="Output JSON file path")
    args = parser.parse_args()

    build_program_dataset(meeting_code=args.meeting, output_path=args.output)
