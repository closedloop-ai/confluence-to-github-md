# Confluence Export to GitHub Markdown

> *We killed Confluence with 14 KB*

[![GitHub release](https://img.shields.io/github/v/release/closedloop-ai/confluence-to-github-md?style=flat-square)](https://github.com/closedloop-ai/confluence-to-github-md/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-blueviolet?style=flat-square&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0wIDE4Yy00LjQyIDAtOC0zLjU4LTgtOHMzLjU4LTggOC04IDggMy41OCA4IDgtMy41OCA4LTggOHoiLz48L3N2Zz4=)](https://github.com/closedloop-ai/confluence-to-github-md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Git LFS](https://img.shields.io/badge/Git-LFS-F05032?style=flat-square&logo=git&logoColor=white)](https://git-lfs.github.com)
[![Confluence](https://img.shields.io/badge/Confluence-XML_export-0052CC?style=flat-square&logo=confluence&logoColor=white)](https://www.atlassian.com/software/confluence)

A Claude Code plugin that converts Confluence XML site exports into clean Markdown GitHub repositories — with full space/page hierarchy, attachments via Git LFS, and zero manual effort.

**18,000+ pages? One command. Two minutes.**

## What it does

1. Parses Confluence XML exports (memory-efficient — handles millions of lines)
2. Deduplicates page versions (keeps only the latest)
3. Converts Confluence HTML to clean Markdown (macros, JIRA links, user mentions, code blocks, images, emoticons)
4. Preserves space/page hierarchy as nested directories
5. Copies attachments alongside their pages
6. Creates a private GitHub repo with Git LFS for large binaries
7. Commits and pushes everything

## Install

```bash
/plugin install closedloop-ai/confluence-to-github-md
```

## Usage

```
/confluence-to-github ~/Downloads/Confluence-export my-org
```

```
/confluence-to-github ~/Downloads/Confluence-export my-org my-wiki-archive
```

| Argument | Description | Required |
|----------|-------------|----------|
| 1st | Path to Confluence export directory (must contain `entities.xml`) | Yes |
| 2nd | GitHub organization or user | Yes |
| 3rd | Repository name (default: `confluence-archive`) | No |

## Requirements

- **Python 3.10+** with `lxml`, `beautifulsoup4`, `markdownify` (auto-installed)
- **GitHub CLI** (`gh`) authenticated with repo-create permissions
- **Git LFS** (auto-installed via Homebrew if missing)

## How to export from Confluence

1. Go to **Confluence Admin** > **Backup & Restore** (or **Space Settings** > **Content Tools** > **Export**)
2. Choose **XML export** (full site or single space)
3. Download the `.zip` and extract it — you'll get a directory with `entities.xml`, `attachments/`, etc.
4. Point the plugin at that directory

## What gets converted

| Confluence feature | Markdown output |
|---|---|
| Pages with children | Directory with `index.md` + child pages |
| Leaf pages | `page-title.md` |
| Info/Note/Warning/Tip boxes | `> **INFO:** ...` blockquotes |
| Code blocks | Fenced code blocks |
| JIRA links | `[PROJ-123]` |
| User mentions | `@user` |
| Images | `![alt](attachments/filename)` |
| Tables | Markdown tables |
| Emoticons | Unicode emoji |
| Blog posts | `blog/YYYY-MM-DD-title.md` |

## Git LFS tracking

Large binary attachments are automatically tracked via Git LFS:

`*.mov` `*.mp4` `*.avi` `*.tar` `*.tar.gz` `*.zip` `*.exe` `*.dmg` `*.key` `*.pptx` `*.xlsx` `*.jar` `*.pdf` `*.psd` `*.ai` `*.sketch`

## License

MIT
