---
name: confluence-to-github
description: "We killed Confluence with 14 KB. Convert a Confluence XML site export into a private GitHub repo of clean Markdown with Git LFS — spaces, pages, hierarchy, and attachments preserved."
disable-model-invocation: true
user-invocable: true
argument-hint: <export-path> <github-org> [repo-name]
allowed-tools: Read, Bash, Write, Glob, Grep
---

# We killed Confluence with 14 KB

Convert a Confluence XML site export into a private GitHub repository of clean
Markdown, organized by space and page hierarchy, with large attachments tracked
via Git LFS.

## Arguments

| Position | Placeholder | Description | Required |
|----------|-------------|-------------|----------|
| 1st | `$0` | Path to Confluence export directory (must contain `entities.xml`) | Yes |
| 2nd | `$1` | GitHub organization or user | Yes |
| 3rd | `$2` | Repository name (default: `confluence-archive`) | No |

## Pre-flight

Verify all four gates. Stop and report on first failure.

1. **Export exists:** `test -f "$0/entities.xml"`
2. **Python deps:**
   ```bash
   python3 -c "import lxml, bs4, markdownify" 2>/dev/null || {
     python3 -m venv /tmp/confluence-env &&
     source /tmp/confluence-env/bin/activate &&
     pip install lxml beautifulsoup4 markdownify
   }
   ```
   Only if venv fails, fall back to `pip3 install --break-system-packages lxml beautifulsoup4 markdownify`.
3. **GitHub CLI:** `gh auth status && gh repo list $1 --limit 1`
4. **Git LFS:** `git lfs version || brew install git-lfs`

## Steps

### 1. Convert

```bash
OUTPUT_DIR="$(mktemp -d)/confluence-markdown"
python3 "${CLAUDE_SKILL_DIR}/scripts/confluence-to-md.py" "$0" "$OUTPUT_DIR"
```

If the script fails: check `head -5 "$0/entities.xml"` for validity. The script uses
iterparse so memory is rarely an issue — if it is, the machine needs more swap.

### 2. Create repo

```bash
gh repo create "$1/${2:-confluence-archive}" --private \
  --description "Confluence wiki archive — converted to Markdown"
```

If 422 (exists), ask the user: overwrite or pick a new name.

### 3. Init git + LFS

```bash
cd "$OUTPUT_DIR"
git init && git branch -m main
git remote add origin "https://github.com/$1/${2:-confluence-archive}.git"
git lfs install
git lfs track \
  "*.mov" "*.mp4" "*.avi" "*.mkv" \
  "*.tar" "*.tar.gz" "*.tgz" "*.zip" "*.rar" "*.7z" \
  "*.exe" "*.msi" "*.dmg" "*.pkg" \
  "*.key" "*.pptx" "*.ppt" "*.xlsx" "*.xls" \
  "*.jar" "*.war" "*.pdf" \
  "*.psd" "*.ai" "*.sketch"
```

### 4. Commit & push

```bash
git add .gitattributes && git add -A
git commit -m "Import Confluence wiki as Markdown

Converted from Confluence XML export.
Organized by space/page hierarchy. Large binaries via Git LFS."

git push -u origin main
```

### 5. Report

After push, report: repo URL, space/page/blog counts, size breakdown
(markdown vs attachments), any conversion errors or GitHub large-file warnings.

## Error recovery

- **push fails on file size:** find files >100MB not in `.gitattributes`, add their
  extensions to `git lfs track`, `git add .gitattributes`, amend commit, push again.
- **pip install fails everywhere:** `python3 -m pip install --user lxml beautifulsoup4 markdownify`

## Cleanup

Print the temp output directory path. Do NOT auto-delete — the user may want to inspect it.
