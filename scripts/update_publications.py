#!/usr/bin/env python3
"""
update_publications.py

Scrapes publications from https://skiml.snu.ac.kr/publications
and updates publication.html in the leejayyoon.github.io repository.
Zero external dependencies required (uses only standard library).
"""

import argparse
import html as html_lib
import os
import re
import sys
import urllib.request

SOURCE_URL = "https://skiml.snu.ac.kr/publications"
TARGET_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "publication.html")

START_MARKER = "<!-- PUBLICATIONS_START -->"
END_MARKER = "<!-- PUBLICATIONS_END -->"


def fetch_html(url: str) -> str:
    """Fetches HTML content from the given URL."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def clean_text(text: str) -> str:
    """Removes HTML tags, decodes entities, and normalizes whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_authors(author_text: str) -> str:
    """Formats author text and highlights Jay-Yoon Lee in blue."""
    author_text = clean_text(author_text)
    def repl(m):
        name = m.group(1)
        has_star = "*" in name
        star_str = "*" if has_star else ""
        return f'<font color="blue">Jay-Yoon Lee{star_str}</font>'

    formatted = re.sub(r"(\bJay-?[Yy]oon\s+Lee(?:\*|\b))", repl, author_text)
    formatted = re.sub(r"\s*,\s*", ", ", formatted)
    formatted = re.sub(r"\s+<font", " <font", formatted)
    return formatted.strip()


def clean_venue(venue_text: str) -> str:
    """Cleans venue text and fixes span-split typos from Google Sites."""
    venue = clean_text(venue_text)
    # Fix split years like '202 6' -> '2026', '202 0' -> '2020'
    venue = re.sub(r"\b(20\d)\s+(\d)\b", r"\1\2", venue)
    # Fix known Google Sites span breaks
    venue = re.sub(r"\bFi\s+ndings\b", "Findings", venue, flags=re.I)
    venue = re.sub(r"\bE\s+MNLP\b", "EMNLP", venue)
    venue = re.sub(r"\bT\s+ACL\b", "TACL", venue)
    venue = re.sub(r"\s*,\s*", ", ", venue)
    return venue.strip()


def parse_publications(raw_html: str):
    """
    Parses Google Sites HTML into structured sections and papers.
    Returns: list of (section_title, [papers])
    """
    double_br_pattern = re.compile(r"<br\s*/?>\s*(?:<[^>]+>\s*)*<br\s*/?>", re.DOTALL)

    # 1. Locate all section headings
    heading_matches = list(re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", raw_html, re.DOTALL))
    sections = []
    for idx, m in enumerate(heading_matches):
        raw_text = re.sub(r"<[^>]+>", "", m.group(1)).replace("\n", " ")
        compact_text = re.sub(r"\s+", "", raw_text)
        if compact_text == "Preprints" or re.match(r"^~?20\d\d$", compact_text):
            next_pos = heading_matches[idx + 1].start() if idx + 1 < len(heading_matches) else len(raw_html)
            sections.append((compact_text, raw_html[m.end():next_pos]))

    results = []
    for sec_title, sec_html in sections:
        papers = []
        ps = re.findall(r"<p\b[^>]*>(.*?)</p>", sec_html, re.DOTALL)
        for p in ps:
            blocks = double_br_pattern.split(p)
            for b in blocks:
                b_clean = clean_text(b)
                if not re.search(r"Jay-?[Yy]oon\s+Lee", b_clean):
                    continue

                # Extract links
                raw_links = re.findall(
                    r"<a\b[^>]*href=[\"\']([^\'\"]+)[\"\'][^>]*>(.*?)</a>", b, re.DOTALL
                )
                links = []
                seen_urls = set()
                for url, link_text in raw_links:
                    url = url.strip()
                    if url.startswith("#") or "searchtype=author" in url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    raw_lbl = clean_text(link_text).lower()
                    raw_lbl_compact = re.sub(r"[\s\[\]]", "", raw_lbl)
                    if "longer" in raw_lbl_compact:
                        label = "paper: longer version"
                    elif "poster" in raw_lbl_compact:
                        label = "poster"
                    elif "code" in raw_lbl_compact:
                        label = "code"
                    else:
                        label = "paper"
                    links.append({"url": url, "label": label})

                is_coming_soon = bool(re.search(r"coming\s+soon", b, re.I)) and not links

                # Split block into lines using <br>
                lines = [l.strip() for l in re.split(r"<br\s*/?>", b) if l.strip()]

                # Locate author line index
                auth_idx = -1
                for i, line in enumerate(lines):
                    line_clean = clean_text(line)
                    if re.search(r"Jay-?[Yy]oon\s+Lee", line_clean):
                        auth_idx = i
                        break

                if auth_idx == -1:
                    continue

                # Title is composed of lines before auth_idx
                title_parts = lines[:auth_idx]
                title_raw = " ".join(title_parts)
                title_raw = re.sub(r"<a\b[^>]*>.*?</a>", " ", title_raw)
                title_clean = clean_text(title_raw)
                title_clean = re.sub(
                    r"\[\s*(?:paper|code|poster|p\s*o\s*s\s*t\s*e\s*r|camera ready).*?\]",
                    "",
                    title_clean,
                    flags=re.I,
                )
                title_clean = re.sub(r"\[\s*\]", "", title_clean)
                title_clean = re.sub(r"^-\s*", "", title_clean).strip()

                if not title_clean:
                    continue

                authors_formatted = format_authors(lines[auth_idx])

                # Venue is composed of lines after auth_idx
                venue_parts = lines[auth_idx + 1 :]
                venue_raw = " ".join(venue_parts)
                venue_raw = re.sub(r"<a\b[^>]*>.*?</a>", " ", venue_raw)
                venue_formatted = clean_venue(venue_raw)

                papers.append({
                    "title": title_clean,
                    "authors": authors_formatted,
                    "venue": venue_formatted,
                    "links": links,
                    "is_coming_soon": is_coming_soon,
                })

        results.append((sec_title, papers))

    return results


def generate_html(sections_data) -> str:
    """Generates the HTML representation of publications."""
    output = []
    for sec_title, papers in sections_data:
        output.append(f'      <h2 style = "text-align: center;">{sec_title}</h2>')
        output.append("      <ul>")
        for paper in papers:
            title = paper["title"]
            authors = paper["authors"]
            venue = paper["venue"]
            links = paper["links"]
            coming_soon = paper["is_coming_soon"]

            output.append(f"         <li><b>{title}</b><br>")
            output.append(f"            {authors} <br> <span style=\"font-style: italic;\"> {venue} </span><br>")

            links_html = []
            for link in links:
                links_html.append(f'[<a href="{link["url"]}"> {link["label"]} </a>]')
            if coming_soon:
                links_html.append('[<a href=""> Coming Soon! </a>]')
            if links_html:
                output.append(f"            {''.join(links_html)}")
            output.append("         </li>")
        output.append("      </ul>")

    return "\n".join(output)


def update_target_file(target_file: str, new_content: str, dry_run: bool = False) -> bool:
    """Replaces content between START_MARKER and END_MARKER in target_file."""
    if not os.path.exists(target_file):
        print(f"Error: Target file not found: {target_file}", file=sys.stderr)
        return False

    with open(target_file, "r", encoding="utf-8") as f:
        file_content = f.read()

    if START_MARKER not in file_content or END_MARKER not in file_content:
        print(
            f"Error: Markers '{START_MARKER}' and '{END_MARKER}' must exist in {target_file}",
            file=sys.stderr,
        )
        return False

    pattern = re.compile(
        rf"({re.escape(START_MARKER)}\n).*?(\n\s*{re.escape(END_MARKER)})",
        re.DOTALL,
    )

    replacement = rf"\g<1>{new_content}\g<2>"
    updated_file_content, count = pattern.subn(replacement, file_content)

    if count == 0:
        print("Error: Could not substitute content between markers.", file=sys.stderr)
        return False

    if updated_file_content == file_content:
        print("No changes detected. Target file is already up to date.")
        return False

    if dry_run:
        print("[Dry Run] Changes detected. Target file would be updated.")
        return True

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(updated_file_content)

    print(f"Successfully updated {target_file}!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Update publications in publication.html from SKI-ML lab website."
    )
    parser.add_argument("--url", default=SOURCE_URL, help="URL to scrape (default: %(default)s)")
    parser.add_argument("--file", default=TARGET_FILE, help="Path to publication.html (default: %(default)s)")
    parser.add_argument("--local-html", help="Path to a local HTML file for offline testing/parsing")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing changes to file")

    args = parser.parse_args()

    if args.local_html:
        print(f"Reading local HTML from {args.local_html}...")
        with open(args.local_html, "r", encoding="utf-8") as f:
            raw_html = f.read()
    else:
        print(f"Fetching publications from {args.url}...")
        raw_html = fetch_html(args.url)

    print(f"Fetched {len(raw_html)} characters.")
    sections_data = parse_publications(raw_html)

    total_papers = sum(len(p) for _, p in sections_data)
    print(f"Found {len(sections_data)} sections with {total_papers} papers in total.")
    for sec_title, papers in sections_data:
        print(f"  - {sec_title}: {len(papers)} papers")

    new_html = generate_html(sections_data)
    changed = update_target_file(args.file, new_html, dry_run=args.dry_run)
    sys.exit(0 if not changed and not args.dry_run else 0)


if __name__ == "__main__":
    main()

