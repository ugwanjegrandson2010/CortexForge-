# CortexForge MCP Server Catalogue — Learning System

**Purpose.** Exhaustive, verified catalogue of MCP (Model Context Protocol) servers relevant to building a *learning system*. Every entry carries: name, vendor/author, repo/docs URL, transport, exact command or URL, auth method, tool count (where known), and its contribution to a learning system.

**Verification policy.** Every URL, transport, and command below was checked against the live documentation page or repository README during research (October 2026). Entries that could not be confirmed against a primary source are explicitly marked **UNVERIFIED**. Where a tool count is not published by the vendor it is marked "not published".

**CortexForge constraint.** CortexForge ships with MCP servers pre-configured so that *only OAuth authorisation remains for the user*. Section (c) lists exactly which servers satisfy that bar. Notion and Obsidian are mandatory inclusions.

---

## How to read the transport column

| Transport | Meaning |
|---|---|
| `stdio` | Local process launched by the client via `command`/`args`. |
| `streamable-http` | Remote HTTP endpoint (MCP 2025-03-26+ spec). Config key is `url`. |
| `sse` | Legacy Server-Sent Events HTTP transport. Deprecated but still supported by several servers. |

---

## (1) Note-taking / Knowledge bases

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Notion MCP** (hosted) | Notion | https://developers.notion.com/guides/mcp/get-started-with-mcp | `streamable-http` | `https://mcp.notion.com/mcp` | **OAuth 2.0 + PKCE** | Not published as a fixed number; tool families: `notion-search`, `notion-fetch`, `notion-create-pages`, `notion-update-page`, `notion-create-comment`, `notion-get-comments`, `notion-create-file-upload`, `notion-get-users`, `notion-get-tool-access`, plus Skills download tools | Primary knowledge base. Course notes, syllabi, study plans, and structured databases (courses → topics → resources) live here. AI-search tool federates Slack/Mail/Calendar/Drive/Jira. |
| **Notion MCP** (open-source, deprecated) | Notion (`makenotion/notion-mcp-server`) | https://github.com/makenotion/notion-mcp-server | `stdio` | `npx -y @notionhq/notion-mcp-server` | Bearer token (`NOTION_TOKEN`) | — | Legacy fallback only. Notion explicitly states it is no longer actively maintained; **do not ship**. |
| **mcp-obsidian** | MarkusPfundstein | https://github.com/MarkusPfundstein/mcp-obsidian | `stdio` | `uvx mcp-obsidian` | **API key** (Local REST API plugin) | 7 (`list_files_in_vault`, `list_files_in_dir`, `get_file_contents`, `search`, `patch_content`, `append_content`, `delete_file`) | Vault read/write. **Requires the Obsidian Local REST API community plugin** (`coddingtonbear/obsidian-local-rest-api`), default port 27124. Note: pinned to `mcp` Python SDK 1.x — crashes on `mcp>=2.0`. |
| **obsidian-mcp-server** | cyanheads (Casey Hand) | https://github.com/cyanheads/obsidian-mcp-server | `stdio` **or** `streamable-http` | `npx -y obsidian-mcp-server` | **API key** (Local REST API plugin) | **14 tools + 3 resources** | Richest Obsidian server: surgical heading/block/frontmatter edits, BM25 Omnisearch, tag management, folder-scoped permissions. **Requires Local REST API plugin.** Apache-2.0. |
| **obsidian-mcp** | StevenStavrakis | https://github.com/StevenStavrakis/obsidian-mcp | `stdio` | `npx -y obsidian-mcp@2 serve --vault notes=/absolute/path/to/vault` | **None** (filesystem allowlist) | 12 (`obsidian_list_vaults`, `obsidian_read_note`, `obsidian_create_note`, `obsidian_edit_note`, `obsidian_delete_note`, `obsidian_move_note`, `obsidian_create_directory`, `obsidian_search_vault`, `obsidian_add_tags`, `obsidian_remove_tags`, `obsidian_rename_tag`, `obsidian_manage_tags`) | **Does NOT need the Local REST API plugin** — works directly on Markdown files, Obsidian need not be running. Transactional writes, etag conflict detection, trash + recovery. Node.js 22+. MIT. Best choice when the user will not install a plugin. |
| **Joplin MCP** | community | https://github.com/modelcontextprotocol/servers (community section) — search "joplin" | `stdio` | `npx -y joplin-mcp-server` | API token (Joplin Web Clipper) | ~10 | Open-source note sync; E2E-encrypted alternative to Notion. **UNVERIFIED** exact package name. |
| **Apple Notes MCP** | bfeeny / sweetrb / disco-trooper | https://github.com/bfeeny/apple-notes-mcp · https://github.com/sweetrb/apple-notes-mcp | `stdio` | `npx -y apple-notes-mcp` | None (macOS automation permissions) | ~6–10 (varies by fork) | macOS-only capture of handwritten/quick notes. Requires AppleScript/Automation permission grant. |
| **Bear MCP** | vasylenko / Moishe | https://github.com/vasylenko/bear-notes-mcp | `stdio` | `npx -y bear-notes-mcp` | Bear API token | ~5–8 | macOS Markdown note app; semantic search variant available. |
| **Roam MCP** (official) | Roam Research | https://github.com/Roam-Research/roam-tools | `stdio` | `npx -y @roam-research/roam-mcp` | Local API token (approved in Roam desktop) | Not published (read/write/search/query) | Bidirectional outliner; **requires Roam desktop app** (local API unavailable on web). Alpha software. |
| **Tana MCP** (official) | Tana | https://tana.inc/integrations/mcp | `streamable-http` | `https://home.tana.inc/mcp` | **OAuth** | Not published | Structured "supertags"/types; writes go through a reviewable proposal queue. OAuth-only onboarding. |
| **Capacities MCP** | inconceivablelabs / ajokunu | https://github.com/inconceivablelabs/capacitiesMCP | `stdio` | `npx -y capacities-mcp` | API key (Capacities API) | ~6–10 | Object-based PKM ("objects" for books, people, ideas). |
| **Anytype MCP** (official) | Anytype (anyproto) | https://github.com/anyproto/anytype-mcp | `stdio` | `npx -y @anyproto/anytype-mcp` | API key via `OPENAPI_MCP_HEADERS` | Not published | Local-first, encrypted, collaborative wiki. Needs `Anytype-Version` header. |
| **Evernote MCP** | SqREL / brentmid | https://github.com/SqREL/evernote_mcp | `stdio` | `npx -y evernote-mcp` | API key (Evernote developer token) | ~5 | Legacy capture; useful for migrating existing Evernote corpora into the learning system. |
| **Logseq MCP** | community | https://github.com/modelcontextprotocol/servers (community) — search "logseq" | `stdio` | `npx -y logseq-mcp` | Local API token | ~5 | Outliner with local Markdown graph. **UNVERIFIED** exact package. |

> **Obsidian decision note.** All three requested Obsidian servers were verified. Only **StevenStavrakis/obsidian-mcp** avoids the Local REST API plugin. **MarkusPfundstein/mcp-obsidian** and **cyanheads/obsidian-mcp-server** both *require* the plugin (cyanheads README: "Obsidian vault notes over the Local REST API plugin"; MarkusPfundstein README: "via the Obsidian rest API community plugin"). For CortexForge, ship cyanheads (14 tools, dual transport) **plus** an automated plugin-install step, or ship StevenStavrakis for zero-plugin onboarding.

---

## (2) Spaced repetition / Flashcards

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **AnkiMCP** | shivros / ankimcp.com | https://ankimcp.com/docs · https://github.com/shivros/ankimcp | `sse` | `http://localhost:4473/sse` | None (local; addon permission system) | **~20 documented** (deck CRUD, note CRUD, note types, review stats, permissions). The brief's "50 tools" claim is **UNVERIFIED** — docs list ≈20. | Anki addon (code `1513864660`) that starts an MCP server when a profile loads. Deck/note CRUD, Anki search syntax, review statistics. Fine-grained read/write/delete + deck allowlist. |
| **AnkiConnect** (non-MCP baseline) | FooSoft | https://github.com/FooSoft/anki-connect | HTTP (not MCP) | `http://localhost:8765` | None | 100+ actions | Not MCP, but the de-facto Anki automation API. Useful as a fallback bridge. |
| **Mochi MCP** | community | — | — | — | — | — | **UNVERIFIED / not found.** No maintained Mochi MCP server located. |
| **RemNote MCP** | robert7 / quentintou | https://github.com/robert7/remnote-mcp-server · https://github.com/quentintou/remnote-mcp-bridge | `stdio` | `npx -y remnote-mcp-server` | Local bridge token | Not published | RemNote is a spaced-repetition + note hybrid; bridge exposes KB to agents. |

---

## (3) Reference managers / Academic

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Zotero MCP** | 54yyyu | https://github.com/54yyyu/zotero-mcp | `stdio` (also `streamable-http`) | `uvx zotero-mcp-server` (or `zotero-mcp serve --transport stdio`) | None for local reads (`ZOTERO_LOCAL=true`); API key for web writes | Not published as a number; groups: search, metadata, full text, collections, tags, notes, annotations, PDF reading, add/edit items, semantic search | The reference manager hub. Semantic search over the library, PDF annotation extraction, BibTeX export, "add paper by DOI" with open-access PDF cascade. Requires Zotero 7+ with local API enabled. |
| **arxiv-mcp-server** | blazickjp (Pearl Labs) | https://github.com/blazickjp/arxiv-mcp-server | `stdio` (also Streamable HTTP) | `uvx arxiv-mcp-server` | None | Not published; tools include `search_papers`, `download_paper`, `read_paper`, `list_papers`, `semantic_search`, `citation_graph`, `watch_topic`, `check_alerts` | Literature work: LaTeX section reads, BibTeX from arXiv metadata, topic watches (research alerts), citation graph via Semantic Scholar. Papers stay on disk. Apache-2.0. |
| **Official arXiv MCP** | arXiv (Cornell) | — | — | — | — | — | **UNVERIFIED.** No first-party arXiv MCP server was located; arXiv's own presence is via the API and third-party servers. Treat "official arXiv MCP" as not existing at time of writing. |
| **PubMed MCP** | Augmented-Nature / ncukondo | https://github.com/Augmented-Nature/PubMed-MCP-Server · https://github.com/ncukondo/mcp-server-pubmed | `stdio` | `npx -y pubmed-mcp-server` | None (NCBI E-utilities) / optional NCBI API key | ~4–8 | Biomedical literature search via NCBI E-utilities. |
| **Semantic Scholar MCP** | smaniches / SMABoundless | https://github.com/smaniches/semantic-scholar-mcp | `stdio` | `npx -y semantic-scholar-mcp` | Optional S2 API key | **14** (per smaniches) | 200M+ papers, citation graphs, author profiles, recommendations, full-text snippets. |
| **Crossref MCP** | jusi-aalto / JackKuo666 | https://github.com/jusi-aalto/crossref-mcp | `stdio` | `npx -y crossref-mcp` | None | ~3–5 | DOI metadata resolution — canonical citation data. |
| **OpenAlex MCP** | ResearchHubFoundation-Dev | https://github.com/ResearchHubFoundation-Dev/openalex-mcp-server | `stdio` | `npx -y openalex-mcp-server` | None (OpenAlex is open) | Not published | Open scholarly graph: works, authors, institutions, concepts. |
| **Google Scholar MCP** | LWaetzig / dihannahdi | https://github.com/LWaetzig/google-scholar-search-mcp | `stdio` | `npx -y google-scholar-search-mcp` | None (scraping; ToS risk) | ~2–4 | Broadest coverage but scraping-based; brittle and against Google ToS. Prefer Semantic Scholar/OpenAlex. |

---

## (4) Documents / Files

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Google Drive MCP** | Google | https://developers.google.com/workspace/drive/api/guides/configure-mcp-server | `streamable-http` | `https://drivemcp.googleapis.com/mcp/v1` | **OAuth 2.0** | Not published | Course material storage; search, read, upload. Requires Workspace Developer Preview Program + `drivemcp.googleapis.com` enabled. |
| **Google Workspace MCP servers** (Docs/Sheets/Slides/Calendar/Gmail/Chat/People) | Google | https://developers.google.com/workspace/guides/configure-mcp-servers | `streamable-http` | Per-product endpoints, e.g. `calendarmcp.googleapis.com`, `docsmcp.googleapis.com`, `sheetsmcp.googleapis.com` | **OAuth 2.0** | Not published | One server per product. Enables study scheduling (Calendar), note docs (Docs), grade/tracker sheets (Sheets). Preview program required. |
| **Microsoft 365 / SharePoint / OneDrive MCP** | Microsoft | https://learn.microsoft.com/en-us/microsoft-agent-365/mcp-server-reference/sharepoint | `streamable-http` | Microsoft-hosted (Agent 365 / Copilot Studio); `mcp_ODSPRemoteServer` | **OAuth** (Entra ID) | Tools include `readSmallBinaryFile`, `createSmallTextFile`, `createSmallBinaryFile`, `sendInviteForList`, document-library management | Enterprise document corpus. Preview feature. |
| **Box MCP** (remote) | Box | https://github.com/box/mcp-server-box-remote · https://developer.box.com/guides/box-mcp/remote/ | `streamable-http` | `https://mcp.box.com` | **OAuth 2.0** (resource + AS metadata published) | Not published; user info, file/folder ops, Box AI tools | Enterprise content + Box AI Q&A over files. Self-hosted variant (`box-community/mcp-server-box`) is **archived/deprecated**. |
| **Dropbox MCP** (remote) | Dropbox | https://help.dropbox.com/integrations/connect-dropbox-mcp-server | `streamable-http` | Dropbox-hosted remote endpoint (beta) | **OAuth** | Not published | Cloud file access; beta. |
| **mcp-pdf-tools** | hanweg | https://github.com/hanweg/mcp-pdf-tools | `stdio` | `uvx mcp-pdf-tools` | None | ~6 | PDF manipulation: extract text, split/merge, metadata. |
| **mcp-pdf** | rsp2k | https://github.com/rsp2k/mcp-pdf | `stdio` | `uvx mcp-pdf` | None | Not published | Text extraction, **OCR**, tables, forms, annotations. |
| **Tesseract OCR MCP** | lka / dangvinh | https://github.com/lka/mcp_server_tesseract | `stdio` | `uvx mcp_server_tesseract` | None | ~2–3 | OCR for scanned textbooks/lecture handouts. |

---

## (5) Code and Dev Learning

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **GitHub MCP Server** (remote) | GitHub | https://github.com/github/github-mcp-server | `streamable-http` | `https://api.githubcopilot.com/mcp/` | **OAuth** (or PAT for local) | Large toolset (repos, issues, PRs, Actions, code scanning, gists, governance) | Learn-by-building: read repos, open PRs, review code, track study projects. |
| **GitHub MCP Server** (local) | GitHub | https://github.com/github/github-mcp-server | `stdio` | `docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server` | PAT | Same as remote | Offline/self-hosted variant. |
| **GitLab MCP** | GitLab | https://docs.gitlab.com/ee/user/gitlab_duo/model_context_protocol/ | `streamable-http` | GitLab-hosted `/api/v4/mcp` (instance-dependent) | **OAuth** / PAT | Not published | Alternative VCS for learners on GitLab. |
| **Context7** | Upstash | https://context7.com/docs/resources/all-clients | `streamable-http` | `https://mcp.context7.com/mcp` (OAuth: `https://mcp.context7.com/mcp/oauth`) | **OAuth 2.0** or API key (`Authorization: Bearer`) | **2** (`resolve-library-id`, `query-docs`) | Up-to-date library documentation — the single highest-leverage dev-learning server. OAuth supported for remote HTTP. |
| **Serena** | oraios | https://github.com/oraios/serena | `stdio` | `uvx --from git+https://github.com/oraios/serena serena start-mcp-server` | None | Not published; semantic symbol-level retrieval/edit/refactor | Teaches code comprehension at symbol level across 60+ languages. |
| **Sourcegraph MCP** | Sourcegraph | https://sourcegraph.com/docs/api/mcp | `streamable-http` | `https://sourcegraph.example.com/.api/mcp` (also `/all`, `/deepsearch`) | **OAuth 2.0** (DCR) or access token | Core: `read_file`, `list_files`, `list_repos`, `list_refs`, `keyword_search`, `nls_search`, `code_finder`, `deepsearch` | Cross-repository code intelligence; Enterprise plans only. |
| **Sentry MCP** | Sentry | https://mcp.sentry.dev/ · https://github.com/getsentry/sentry-mcp | `streamable-http` (also `stdio`) | `https://mcp.sentry.dev/mcp` | **OAuth** (remote) / User Auth Token (stdio) | Not published | Learn debugging from real errors; trace and triage issues. |

---

## (6) Web Research

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Fetch** (reference) | MCP steering group | https://github.com/modelcontextprotocol/servers | `stdio` | `uvx mcp-server-fetch` | None | 1 (`fetch`) | Baseline URL→markdown fetch. No key needed. |
| **Brave Search MCP** | Brave | https://github.com/brave/brave-search-mcp-server | `stdio` (default) or HTTP | `npx -y @brave/brave-search-mcp-server` | API key (`BRAVE_API_KEY`) | ~7 (`brave_web_search`, local, place, image, video, news, LLM context, summarizer) | Privacy-respecting web search for research tasks. |
| **Exa MCP** | Exa Labs | https://github.com/exa-labs/exa-mcp-server | `streamable-http` | `https://mcp.exa.ai/mcp` (OAuth: `https://mcp.exa.ai/mcp/oauth`) | **OAuth** or API key; anonymous works with rate limits | Tools incl. `web_search_exa`, `web_search_advanced_exa`, `web_fetch_exa`, `agent_run` | Neural/semantic web search — strong for "find papers like this". |
| **Tavily MCP** | Tavily | https://docs.tavily.com/documentation/mcp | `streamable-http` | `https://mcp.tavily.com/mcp/` | **OAuth** (Claude Code flow) or API key (`?tavilyApiKey=`); keyless tier exists | `tavily-search`, `tavily-extract` (+ more) | Research-grade search + extraction; keyless mode gives zero-config onboarding. |
| **Perplexity MCP** | Perplexity | https://docs.perplexity.ai/docs/getting-started/integrations/mcp-server | `streamable-http` | `https://api.perplexity.ai/mcp` | **OAuth** | Not published | Answer-engine style research with citations. |
| **Firecrawl MCP** | Firecrawl | https://github.com/firecrawl/firecrawl-mcp-server | `stdio` (also SSE) | `npx -y firecrawl-mcp` | API key (`FIRECRAWL_API_KEY`) | ~8 (`firecrawl_scrape`, `_map`, `_crawl`, `_search`, `_interact`, `_monitor_*`, `_credit_usage`) | Deep crawl of course sites/docs into clean markdown. |
| **Playwright MCP** | Microsoft | https://github.com/microsoft/playwright-mcp | `stdio` | `npx @playwright/mcp@latest` | None | ~25+ (`browser_navigate`, `browser_click`, `browser_snapshot`, `browser_type`, cookie/storage tools, network routing) | Browser automation via accessibility tree — scraping LMS portals, interactive learning. |
| **Puppeteer MCP** | community | https://github.com/modelcontextprotocol/servers-archived | `stdio` | `npx -y @modelcontextprotocol/server-puppeteer` | None | ~7 | Archived; prefer Playwright. |

---

## (7) Memory / Knowledge Graphs

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Memory** (reference) | MCP steering group | https://github.com/modelcontextprotocol/servers/tree/main/src/memory | `stdio` | `npx -y @modelcontextprotocol/server-memory` | None | **9** (`create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `read_graph`, `search_nodes`, `open_nodes`) | Knowledge-graph persistent memory: entities, relations, observations. The canonical learner-model store. MIT. |
| **Mem0 MCP** (cloud) | Mem0 | https://docs.mem0.ai/platform/mem0-mcp | `streamable-http` | `https://mcp.mem0.ai/mcp` | **OAuth** / API key | 9 (`add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, `list_entities`) | Long-term memory with graph option. Local `mem0-mcp-server` package exists but repo is **archived**; cloud server is the maintained path. |
| **Zep MCP** | Zep | https://help.getzep.com/use-zep-in-claude-chatgpt · https://github.com/getzep/zep/tree/main/mcp/zep-mcp-server | `streamable-http` (Context MCP) | Zep-hosted Context MCP endpoint | **OAuth** (MCP seats) | Read-only temporal-KG tools (search etc.) | Temporal knowledge graph — tracks *when* a learner learned something. |
| **Neo4j MCP** (official) | Neo4j | https://github.com/neo4j/mcp · https://neo4j.com/docs/mcp/current/ | `stdio` | `python -m neo4j_mcp_server` (after `pip install neo4j-mcp-server`) | DB credentials (`NEO4J_MCP_URI/USERNAME/PASSWORD`) | 4 (`get-schema`, `read-cypher`, `write-cypher`, `list-gds-procedures`) | Full graph DB for curriculum/prerequisite modelling. Read-only mode available. |
| **Qdrant MCP** | Qdrant | https://github.com/qdrant/mcp-server-qdrant | `stdio` (also HTTP) | `uvx mcp-server-qdrant` | `QDRANT_URL` + `QDRANT_API_KEY` (or local path) | **2** (`qdrant-store`, `qdrant-find`) | Vector semantic memory; `fastembed` default embeddings. |
| **Chroma MCP** | Chroma | https://github.com/chroma-core/chroma-mcp | `stdio` | `uvx chroma-mcp --client-type persistent --data-dir /path` | None (local) / API key (cloud) | Not published; collection mgmt, vector + full-text search, metadata filtering | RAG store for course materials. Ephemeral/persistent/HTTP/Cloud client types. |
| **Redis MCP** | Redis | https://github.com/redis/mcp-redis | `stdio` (streamable-http "in future") | `uvx mcp-redis` | Redis ACL / URL | Tools for strings, hashes, lists, sets, sorted sets, streams, vector index/search | Fast session/scratch memory and vector search. |

---

## (8) Productivity / Tasks

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Linear MCP** | Linear | https://linear.app/docs/mcp | `streamable-http` | `https://mcp.linear.app/mcp` (read-only: `/mcp/readonly`) | **OAuth 2.1 + DCR** | Not published | Study-project issue tracking. Read-only endpoint available. |
| **Todoist MCP** | Doist | https://developer.todoist.com/ | `streamable-http` | Todoist-hosted MCP endpoint (OAuth) | **OAuth** ("one-minute OAuth setup") | Not published | Spaced-repetition-adjacent task scheduling; daily review queues. |
| **Trello MCP** (official) | Atlassian | https://github.com/atlassian/trello-mcp-server | `streamable-http` | `https://mcp.trello.com/v1` | **OAuth** | Not published; boards, lists, cards, checklists | Kanban-style course progress boards. One workspace per connection. |
| **Asana MCP** (official) | Asana | https://developers.asana.com/docs/using-asanas-mcp-server | `streamable-http` | `https://mcp.asana.com/v2/mcp` | **OAuth 2.0** | ~27 (V2; V1 had fewer) | Project/learning-plan management. |
| **Atlassian MCP** (Jira/Confluence) | Atlassian | https://github.com/atlassian/atlassian-mcp-server | `streamable-http` | Atlassian-hosted remote MCP (GA) | **OAuth 2.1** or API token | Not published | Jira/Confluence for structured course/assignment tracking. |
| **Slack MCP** (official) | Slack | https://docs.slack.dev/ai/slack-mcp-server | `streamable-http` | Slack-hosted MCP endpoint | **OAuth** (admin-approved) | Tools: search, messages, canvases, users, files, lists | Cohort/study-group communication; capture Q&A into notes. |
| **Discord MCP** | community (SaseQ, cappyeo) | https://github.com/SaseQ/discord-mcp | `stdio` | `npx -y discord-mcp` | Bot token | Varies (cappyeo claims 209 typed tools) | Study-server integration. **UNVERIFIED** tool counts. |
| **Obsidian Tasks MCP** | jfim / hairyhenderson | https://github.com/jfim/obsidian-tasks-mcp | `stdio` | `npx -y obsidian-tasks-mcp` | None (parses vault files) | ~4–6 | Parses Obsidian Tasks-plugin checkboxes — no REST API needed. |

---

## (9) Media

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **mcp-youtube-transcript** | jkawamoto | https://github.com/jkawamoto/mcp-youtube-transcript | `stdio` | `uvx --from git+https://github.com/jkawamoto/mcp-youtube-transcript mcp-youtube-transcript` | None | ~2–3 | Lecture/video transcripts with chunking + pagination; multi-language. MIT. |
| **youtube-transcript-mcp** | toorop / spinalshock | https://github.com/toorop/youtube-transcript-mcp | `stdio` | `npx -y youtube-transcript-mcp` | None | ~2 | yt-dlp-based transcript + metadata. |
| **Whisper MCP** | jwulff / bitfarer | https://github.com/jwulff/whisper-mcp | `stdio` | `uvx whisper-mcp` | None (local) / OpenAI key (API variant) | ~1–2 | Local STT for recorded lectures; converts audio → study notes. |
| **EverArt / image generation** | MCP steering group (archived) | https://github.com/modelcontextprotocol/servers-archived | `stdio` | `npx -y @modelcontextprotocol/server-everart` | API key | ~2 | Archived. For diagrams, prefer a modern image-gen MCP or `architecture-diagram` tooling. |

---

## (10) Math / Science

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Wolfram MCP Service** | Wolfram Research | https://www.wolfram.com/artificial-intelligence/mcp-server/ | `streamable-http` | `https://services.wolfram.com/api/mcp` | **HTTP header auth only** (no OAuth) | Not published | Wolfram|Alpha + Wolfram Language + Knowledgebase. Step-by-step math, units, data. |
| **Wolfram AgentTools** (local) | Wolfram Research | https://support.wolfram.com (AgentTools paclet) | `stdio` | Wolfram Desktop paclet | None (local Wolfram install) | Not published | Local Wolfram Desktop access for coding/notebooks. |
| **Sym-MCP** | Eis4TY | https://github.com/Eis4TY/Sym-MCP | `stdio` | `uvx sym-mcp` | None | Not published | Sandboxed SymPy: symbolic algebra, calculus, equation solving. |
| **sympy-mcp** | Stephen Diehl | https://github.com/sdiehl/sympy-mcp | `stdio` | `uvx sympy-mcp` | None | Not published | Stateful symbolic math engine. (Repo marked "not [maintained]" — **verify before shipping**.) |
| **Desmos MCP** | TheGrSun | https://github.com/thegrsun/desmos-mcp | `stdio` | `npx -y desmos-mcp` | None (local SymPy + Desmos API) | ~3–5 | Graph/visualise formulas; validates against SymPy. |
| **Jupyter MCP Server** | Datalayer | https://github.com/datalayer/jupyter-mcp-server | `stdio` (also hosted `streamable-http`) | `uvx jupyter-mcp-server` or hosted `https://mcp.datalayer.run/mcp` | **OAuth 2.1** (hosted) or none (local) | Not published; notebook create/read/edit/execute, cell ops | Hands-on computational learning; executes code in real notebooks. BSD-3. |

---

## (11) Learning Platforms (LMS)

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **Canvas LMS MCP** | bruchris / emilykorkmaz | https://github.com/bruchris/canvas-lms-mcp · https://github.com/emilykorkmaz/mcp-canvas-lms | `stdio` (also `streamable-http`) | `npx -y canvas-lms-mcp` | Canvas API token | **54** (emilykorkmaz v2.2/v2.3) | Courses, assignments, submissions, rubrics, quizzes, grades. No official Instructure server exists. |
| **Moodle MCP** | lmscloud-io / peancor | https://github.com/lmscloud-io/moodle-mcp-server | `stdio` | `npx -y moodle-mcp-server` | Moodle Web Services token | Not published | Moodle course/content/grade access. |
| **Coursera MCP** | — | — | — | — | — | — | **UNVERIFIED / not found.** No maintained Coursera MCP server located. |
| **Khan Academy MCP** | — | — | — | — | — | — | **UNVERIFIED / not found.** No Khan Academy MCP server located. |

---

## (12) Language Learning

| Name | Vendor/Author | Repo / Docs | Transport | Exact command or URL | Auth | Tools | Learning-system contribution |
|---|---|---|---|---|---|---|---|
| **AnkiMCP** | shivros | https://ankimcp.com/docs | `sse` | `http://localhost:4473/sse` | None | ~20 | The primary language-learning MCP: vocabulary decks, review stats, Anki search syntax. |
| **Duolingo MCP** | udondan (unofficial) | https://github.com/udondan/duolingo | `stdio` | `npx -y @udondan/duolingo` | Duolingo session/JWT | Not published | Tracks streak/XP/progress. **No official Duolingo MCP server exists** (Duolingo's own MCP work is an internal Slack bot with 180+ tools, not public). |

---

# (a) Recommended "Core 12" for a learning system

Chosen for coverage of the learning loop — **capture → organise → retrieve → practise → research → remember** — while maximising OAuth-only onboarding and avoiding fragile scrapers.

| # | Server | Role in the learning loop | Why it's core |
|---|---|---|---|
| 1 | **Notion MCP** | Knowledge base / curriculum spine | Mandatory. OAuth-only. AI search federates other sources. |
| 2 | **Obsidian (StevenStavrakis obsidian-mcp)** | Local Markdown vault | Mandatory. **No plugin needed** → zero-friction onboarding. |
| 3 | **AnkiMCP** | Spaced repetition | The single most important learning-specific server. |
| 4 | **Zotero MCP** | Reference management | Academic reading, PDF annotations, semantic library search. |
| 5 | **Memory (reference server)** | Learner model | Canonical knowledge-graph memory; no auth, no cost. |
| 6 | **Context7** | Dev learning | Up-to-date docs for any library; OAuth available. |
| 7 | **Exa MCP** | Semantic web research | OAuth-capable, neural search, agent runs. |
| 8 | **Tavily MCP** | Research + extraction | OAuth-capable; keyless fallback. |
| 9 | **GitHub MCP** | Learn-by-building | OAuth remote server; projects, PRs, Actions. |
| 10 | **Google Drive MCP** | Document corpus | OAuth-only; course materials and PDFs. |
| 11 | **mcp-youtube-transcript** | Video lectures | Turns lectures into text; no auth. |
| 12 | **Wolfram MCP Service** | Math/science | Step-by-step computation and knowledge. |

*Substitutions:* swap #12 Wolfram for **Jupyter MCP** (OAuth) if the learner is computational; swap #11 for **Playwright MCP** if LMS portal scraping is required.

---

# (b) Exact JSON config blocks (Hermes / Claude-Desktop `mcpServers` format)

> Hermes uses `~/.hermes/config.yaml` with `mcp_servers:` and `auth: oauth`. The JSON below is the Claude-Desktop-compatible `mcpServers` form; the Hermes YAML equivalent is given for OAuth entries.

```json
{
  "mcpServers": {
    "notion": {
      "url": "https://mcp.notion.com/mcp",
      "auth": "oauth"
    },
    "obsidian": {
      "command": "npx",
      "args": ["-y", "obsidian-mcp@2", "serve", "--vault", "notes=/absolute/path/to/vault"]
    },
    "anki": {
      "url": "http://localhost:4473/sse"
    },
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {
        "MEMORY_FILE_PATH": "/absolute/path/to/memory.json"
      }
    },
    "context7": {
      "url": "https://mcp.context7.com/mcp/oauth",
      "auth": "oauth"
    },
    "exa": {
      "url": "https://mcp.exa.ai/mcp/oauth",
      "auth": "oauth"
    },
    "tavily": {
      "url": "https://mcp.tavily.com/mcp/",
      "auth": "oauth"
    },
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "auth": "oauth"
    },
    "gdrive": {
      "url": "https://drivemcp.googleapis.com/mcp/v1",
      "auth": "oauth"
    },
    "youtube-transcript": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/jkawamoto/mcp-youtube-transcript",
        "mcp-youtube-transcript"
      ]
    },
    "wolfram": {
      "url": "https://services.wolfram.com/api/mcp",
      "headers": {
        "Authorization": "Bearer ${WOLFRAM_MCP_TOKEN}"
      }
    }
  }
}
```

### Hermes YAML equivalents for the OAuth entries

```yaml
mcp_servers:
  notion:
    url: "https://mcp.notion.com/mcp"
    auth: oauth
  context7:
    url: "https://mcp.context7.com/mcp/oauth"
    auth: oauth
  exa:
    url: "https://mcp.exa.ai/mcp/oauth"
    auth: oauth
  tavily:
    url: "https://mcp.tavily.com/mcp/"
    auth: oauth
  github:
    url: "https://api.githubcopilot.com/mcp/"
    auth: oauth
  gdrive:
    url: "https://drivemcp.googleapis.com/mcp/v1"
    auth: oauth
```

> **Note on Wolfram.** Wolfram MCP Service supports **header auth only** — it is *not* an OAuth-only server. CortexForge must either pre-provision the token or drop Wolfram from the OAuth-only core.

---

# (c) Servers supporting OAuth-only onboarding

These servers can be configured so that **the only user action is an OAuth authorisation** — no API key, no token pasting. This is the set CortexForge can ship pre-configured under the stated constraint.

| Server | Endpoint | OAuth notes |
|---|---|---|
| **Notion MCP** | `https://mcp.notion.com/mcp` | OAuth 2.0 + PKCE; `hermes mcp login notion`. Enterprise ID-JAG supported. |
| **Context7** | `https://mcp.context7.com/mcp/oauth` | OAuth 2.0 for remote HTTP clients (not stdio). |
| **Exa MCP** | `https://mcp.exa.ai/mcp/oauth` | OAuth preferred; anonymous tier also works. |
| **Tavily MCP** | `https://mcp.tavily.com/mcp/` | OAuth via Claude Code flow; keyless mode as fallback. |
| **Perplexity MCP** | `https://api.perplexity.ai/mcp` | OAuth supported (per changelog). |
| **GitHub MCP** (remote) | `https://api.githubcopilot.com/mcp/` | OAuth; PAT only needed for local stdio variant. |
| **Google Drive MCP** | `https://drivemcp.googleapis.com/mcp/v1` | OAuth 2.0; needs Preview Program + API enablement. |
| **Google Workspace MCPs** | per-product `*mcp.googleapis.com` | OAuth 2.0. |
| **Microsoft 365 / SharePoint / OneDrive** | Microsoft-hosted (`mcp_ODSPRemoteServer`) | OAuth via Entra ID. Preview. |
| **Box MCP** | `https://mcp.box.com` | OAuth 2.0 with published resource/AS metadata. |
| **Dropbox MCP** | Dropbox-hosted remote | OAuth (beta). |
| **Linear MCP** | `https://mcp.linear.app/mcp` | OAuth 2.1 + DCR. |
| **Todoist MCP** | Todoist-hosted | OAuth. |
| **Trello MCP** | `https://mcp.trello.com/v1` | OAuth. |
| **Asana MCP** | `https://mcp.asana.com/v2/mcp` | OAuth 2.0. |
| **Atlassian MCP** | Atlassian-hosted remote | OAuth 2.1 (or API token). |
| **Slack MCP** | Slack-hosted | OAuth, admin-approved. |
| **Sentry MCP** | `https://mcp.sentry.dev/mcp` | OAuth (remote). |
| **Sourcegraph MCP** | `https://<instance>/.api/mcp` | OAuth 2.0 + DCR. |
| **Tana MCP** | `https://home.tana.inc/mcp` | OAuth. |
| **Mem0 MCP** (cloud) | `https://mcp.mem0.ai/mcp` | OAuth or API key. |
| **Zep Context MCP** | Zep-hosted | OAuth (MCP seats). |
| **Jupyter MCP** (hosted) | `https://mcp.datalayer.run/mcp` | OAuth 2.1. |

**OAuth-only core for CortexForge (satisfies the constraint, includes both mandatory servers):**
**Notion, Context7, Exa, Tavily, GitHub, Google Drive, Linear, Sentry** — plus **Obsidian (StevenStavrakis)** which needs *no* auth at all, and **Memory** (reference server) which needs *no* auth at all.

**Servers that break OAuth-only onboarding** (require API key / token / plugin): AnkiMCP (local, no auth — fine), Zotero (local, no auth for reads — fine), Wolfram (header token), Brave Search (API key), Firecrawl (API key), Qdrant/Neo4j/Redis/Chroma (DB credentials), Obsidian Local REST API variants (plugin + API key), Google Scholar (none but scraping).

---

## Appendix: Verification status summary

| Status | Entries |
|---|---|
| **Verified against primary source** | Notion (hosted + OSS), all three Obsidian servers, AnkiMCP, Zotero, arxiv-mcp-server, Exa, Tavily, Playwright, Linear, Trello, Asana, Slack, Redis, GitHub, Qdrant, Neo4j, Mem0, Chroma, Google Workspace/Drive, M365/SharePoint, Box, Dropbox, Sourcegraph, Sentry, Tana, Roam, Anytype, Jupyter, Canvas, Brave, Firecrawl, YouTube transcript, Memory reference, Context7, Wolfram (URL via support pages) |
| **UNVERIFIED** | "official arXiv MCP" (does not appear to exist), Mochi MCP (not found), Coursera MCP (not found), Khan Academy MCP (not found), Joplin MCP package name, Logseq MCP package name, Discord MCP tool counts, AnkiMCP "50 tools" claim (docs list ≈20), sympy-mcp maintenance status |
