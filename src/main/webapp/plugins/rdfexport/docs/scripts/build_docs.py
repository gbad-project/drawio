import shutil
import re
import subprocess
import sys
from pathlib import Path
import os

# --- Configuration ---
# Get the directory of the current script (docs/scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent # Go up two levels from docs/scripts/ to project root
DOCS_DIR = PROJECT_ROOT / 'docs'
SOURCE_DIR = DOCS_DIR / 'source'
CONTENT_DIR = SOURCE_DIR / 'content' # Where processed files will go

# Directories to copy Markdown files from (relative to PROJECT_ROOT)
COPY_SOURCES = [
    (Path('README.md'), Path('')), # Root README.md
    (Path('aicode/python_core'), Path('python_core')), # Python core docs
    (Path('examples'), Path('examples')), # Examples
    (Path('aicode/.context'), Path('aicode/.context')), # AICode context artifacts
    (Path('aicode/.reports'), Path('aicode/.reports')), # AICode reports artifacts
    (Path('aicode/.chats'), Path('aicode/.chats')), # AICode chats artifacts
    (Path('data/fixtures'), Path('data/fixtures')), # Data fixtures
]

# GFM alert regex and replacement patterns
# This regex captures the alert type and any optional title
GFM_ALERT_START_REGEX = re.compile(r'^>\s*!\[(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$', re.IGNORECASE)
# Regex to check for an existing H1 heading
H1_REGEX = re.compile(r'^\s*#\s+.*$', re.MULTILINE)
# Regex to find relative Markdown links
MD_LINK_REGEX = re.compile(r'(\[.*?\])\((?!\w+://)(?!#)(\.{1,2}/.*?)\)')

# --- Helper Functions ---
def clean_and_create_content_dir():
    if CONTENT_DIR.exists():
        shutil.rmtree(CONTENT_DIR)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Cleaned and created: {CONTENT_DIR}")

def fix_relative_paths(content: str, src_path: Path, dest_path: Path) -> str:
    """
    Fix relative paths in Markdown content.
    """
    def replacer(match):
        link_text = match.group(1)
        relative_path = match.group(2)

        # Path of the original source file
        original_dir = src_path.parent
        # Resolve the absolute path of the linked file from the original location
        target_abs_path = (original_dir / relative_path).resolve()

        # Path of the destination file
        new_dir = dest_path.parent
        # Calculate the new relative path from the new location
        try:
            new_relative_path = Path(os.path.relpath(target_abs_path, new_dir))
            # Convert to forward slashes for Markdown links
            new_relative_path_str = str(new_relative_path).replace('\\', '/')
            print(f"  - Rewriting link: '{relative_path}' -> '{new_relative_path_str}'")
            return f"{link_text}({new_relative_path_str})"
        except ValueError:
            # This can happen if paths are on different drives on Windows
            print(f"  - Could not rewrite link: '{relative_path}' (different drive?)")
            return match.group(0) # Return original link

    return MD_LINK_REGEX.sub(replacer, content)

def process_markdown_file(src_path: Path, dest_path: Path):
    with src_path.open('r', encoding='utf-8') as f:
        lines = f.readlines()

    processed_lines = []
    in_gfm_alert = False
    for line in lines:
        match = GFM_ALERT_START_REGEX.match(line)
        if match:
            if in_gfm_alert: # Close previous alert if nested (shouldn\'t happen with GFM)
                processed_lines.append('```\n')
            alert_type = match.group(1).lower()
            title = match.group(2).strip()
            if title:
                processed_lines.append(f'```{{{alert_type}}} {title}\n')
            else:
                processed_lines.append(f'```{{{alert_type}}}\n')
            in_gfm_alert = True
            # Add the content of the first line of the alert, stripping the '>'
            content_start = line[match.end():].strip()
            if content_start:
                processed_lines.append(content_start + '\n')
        elif in_gfm_alert and line.startswith('>'):
            # Continue alert block, strip '>'
            processed_lines.append(line[1:].lstrip())
        else:
            if in_gfm_alert: # End of alert block
                processed_lines.append('```\n')
                in_gfm_alert = False
            processed_lines.append(line)

    if in_gfm_alert: # Close any unclosed alert at EOF
        processed_lines.append('```\n')

    final_content = "".join(processed_lines)

    # Fix relative paths
    final_content = fix_relative_paths(final_content, src_path, dest_path)

    # Check if an H1 heading exists, if not, add one from the filename
    if not H1_REGEX.search(final_content):
        # Convert filename to a title (e.g., "my_file.md" -> "My File")
        title = dest_path.stem.replace('_', ' ').replace('-', ' ').title()
        final_content = f"# {title}\n\n" + final_content

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open('w', encoding='utf-8') as f:
        f.write(final_content)
    print(f"Processed and copied: {src_path} to {dest_path}")

def copy_and_process_sources():
    for src_relative_path, dest_sub_dir in COPY_SOURCES:
        src_full_path = PROJECT_ROOT / src_relative_path
        dest_full_path = CONTENT_DIR / dest_sub_dir

        print(f"\n--- Processing Source: {src_relative_path} ---")
        print(f"  src_full_path: {src_full_path}")
        print(f"  dest_full_path: {dest_full_path}")

        if not src_full_path.exists():
            print(f"Warning: Source path not found: {src_full_path}")
            continue

        if src_full_path.is_file():
            if src_full_path.suffix == '.md':
                process_markdown_file(src_full_path, dest_full_path / src_full_path.name)
            elif src_full_path.suffix == '.txt':
                dest_full_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_full_path, dest_full_path / src_full_path.name)
                print(f"Copied: {src_full_path} to {dest_full_path / src_full_path.name}")
            else:
                print(f"Skipping non-Markdown/text file: {src_full_path}")
        elif src_full_path.is_dir():
            dest_full_path.mkdir(parents=True, exist_ok=True) # Create the base destination directory
            for file_src_path in src_full_path.rglob('*.md'):
                # Exclude files in 'data/fixtures/external' if the current source is 'data/fixtures'
                if src_relative_path == Path('data/fixtures') and 'external' in file_src_path.parts:
                    print(f"  - Skipping MD in external: {file_src_path}")
                    continue

                relative_to_src = file_src_path.relative_to(src_full_path)
                file_dest_path = dest_full_path / relative_to_src
                print(f"  - Found MD: {file_src_path} -> {file_dest_path}")
                process_markdown_file(file_src_path, file_dest_path)
            for file_src_path in src_full_path.rglob('*.txt'):
                relative_to_src = file_src_path.relative_to(src_full_path)
                
                # 1. Copy the original .txt file to the content directory
                file_dest_path_txt = dest_full_path / relative_to_src
                file_dest_path_txt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_src_path, file_dest_path_txt)
                print(f"Copied original TXT: {file_src_path} to {file_dest_path_txt}")

                # 2. Create an accompanying .rst file that literally includes the .txt file
                file_dest_path_rst = dest_full_path / relative_to_src.with_suffix('.rst')
                
                # The include path should be relative from the .rst file to the .txt file
                # Since they are in the same directory, it's just the filename
                rst_content = f".. include:: {relative_to_src.name}\n   :literal:\n"
                
                # Add a title to the .rst file for toctree to pick up
                title = relative_to_src.stem.replace('_', ' ').replace('-', ' ').title()
                underline = '=' * len(title)
                rst_content = f"{title}\n{underline}\n\n" + rst_content

                file_dest_path_rst.parent.mkdir(parents=True, exist_ok=True)
                with open(file_dest_path_rst, 'w', encoding='utf-8') as f:
                    f.write(rst_content)
                print(f"Generated RST for literal include: {file_dest_path_rst}")
        else:
            print(f"Skipping unknown path type: {src_full_path}")


# --- Main Execution ---
if __name__ == "__main__":
    clean_and_create_content_dir()
    copy_and_process_sources()
    # AICODE-NOTE: DO NOT REMOVE!
    # signed-off: human
    # optional: currently
    # the build is undertaken
    # by make and orchestrated
    # by bun via package.json
    # run_sphinx_build()