import os
import shutil
import sys

from scrape_mygov_comments import main

# This path correctly places the output files where the React dashboard can access them.
OUTPUT_DIR = os.path.join("dashboard", "public", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# The two target URLs.
SITE1 = "https://www.mygov.in/group-issue/inviting-ideas-mann-ki-baat-prime-minister-narendra-modi-28th-september-2025/"
SITE2 = "https://www.mygov.in/group-issue/inviting-comments-draft-indian-language-standard-akshar-hindi-language/"


def safe_replace(src_filename, dst_filename):
    """Safely copies the processed file to dashboard/public and outputs/ (site-specific)."""
    try:
        src_path = os.path.join("outputs", src_filename)
        dashboard_dst_path = os.path.join(OUTPUT_DIR, dst_filename)
        archive_dst_path = os.path.join("outputs", dst_filename)

        if not os.path.exists(src_path):
            print(f"Warning: Source file not found at {src_path}. Skipping copy.", file=sys.stderr)
            return

        shutil.copy2(src_path, dashboard_dst_path)
        shutil.copy2(src_path, archive_dst_path)
    except Exception as e:
        print(f"Error: Failed to copy file {src_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    # --- Scrape Site 1 ---
    print(">>> Scraping Mann Ki Baat (Site 1)...")
    main(SITE1)
    safe_replace("comments_processed.csv", "comments_processed_site1.csv")

    # --- Scrape Site 2 ---
    print("\n>>> Scraping Akshar Hindi (Site 2)...")
    main(SITE2)
    safe_replace("comments_processed.csv", "comments_processed_site2.csv")

    print(f"\nScraping complete. All files are saved in: {os.path.abspath(OUTPUT_DIR)}")
