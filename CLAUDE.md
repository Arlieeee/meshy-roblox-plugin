# CLAUDE.md — Meshy DCC Integration Documentation Guide

This file is a **reference for writing documentation** for this DCC integration. It is not active during normal development — only follow the workflow below when the user explicitly asks to write documentation.

Place a copy of this file in each DCC plugin repo. When writing docs, read the local plugin implementation and the webapp to derive all plugin-specific content; this file only describes the format conventions to follow.

---

## When to Use This Guide

**Only when the user explicitly asks to write documentation** (e.g., "let's write the docs", "start the documentation", "write the Meshy docs for this plugin").

When that happens, respond with:

> "I'll read the implementation here and in the webapp first, then present a documentation plan for you to confirm before writing anything. Shall I start?"

Proceed only after explicit confirmation. During all other development work, ignore the workflow below and focus on the task at hand.

---

## Step-by-Step Workflow

### Step 0 — Confirm Before Starting

Only enter this workflow when the user explicitly asks to write documentation. Do not start any steps below on your own initiative.

When the user asks to begin, respond with the prompt from the "When to Use This Guide" section above and wait for confirmation before reading any files.

---

### Step 1 — Read This Plugin Repo

Read the following to understand what was built:

- `README.md` — feature summary, architecture, API endpoints, how users run it
- Main implementation file(s) — endpoints, logic, file format handling, auth model
- Any config or type files relevant to the feature surface

**Goal**: Understand what the plugin/bridge does, what endpoints it exposes, what file formats it supports, how users install or run it, and whether it requires any account or authentication.

---

### Step 2 — Find and Read the Webapp Implementation

Look for the Meshy webapp at these paths relative to this repo (try each):

```
../meshy-webapp/
../../webapp/meshy-webapp/
../webapp/meshy-webapp/
```

Once found, search for and read the following:

- `components/{platform}/` — all files (types, store, api, hooks, dialogs)
- `components/workspace*/Viewport/Toolbar/hooks/usePluginPopover.tsx` — DCC Bridge menu entry
- `constants/links.ts` — download links, documentation links, platform-specific URLs
- Any component files matching `*{Platform}*`

**Goal**: Understand the full user-facing flow — UI states, dialog copy, error messages, what the user sees at each step — so the documentation matches the actual product.

---

### Step 3 — Present Plan for User Confirmation

Before writing anything, output a structured plan and **wait for the user to approve or correct it**.

```
## Documentation Plan — Please Confirm

**Plugin docs folder**: {plugin}-plugin  (e.g., roblox-plugin, unity-plugin)
**Platform display name**: {Tool}  (e.g., Roblox Studio, Unity)
**Integration type**: [Type 1 / Type 2 / Type 2 + OAuth]  — see Integration Types below

**Pages to create**:
  - introduction      → covers: [what the plugin does, requirements, how to install/run]
  - bridge-to-{plugin} → covers: [key user flow steps]
  - troubleshooting   → covers: [main error scenarios]  ← only if there are enough error cases

**Key user flows identified**:
  1. First-time user: [step-by-step]
  2. Returning user: [step-by-step]

**Webapp files read**:
  - [list the files you actually read]

**Anything to adjust before I start writing?**
```

Do not proceed past this point until the user replies with confirmation (or corrections).

---

### Step 4 — Write Draft in `docs-draft/`

After the user confirms the plan, create a `docs-draft/` folder in this repo and write one `.en.mdx` file per page:

```
docs-draft/
├── introduction.en.mdx
├── bridge-to-{plugin}.en.mdx
└── troubleshooting.en.mdx    ← only if applicable
```

Follow all format rules from the **MDX Format Reference** section below.

After writing, tell the user:

> "Drafts are in `docs-draft/`. Please review the content. When ready, provide: (1) the absolute path to your local meshy-docs repo, and (2) the git branch to check out or create."

---

### Step 5 — Ask for Docs Repo Details

Ask the user:

1. "What is the absolute path to your local meshy-docs repo?" (e.g., `/Users/xxx/meshy-portals/meshy-docs`)
2. "Which branch should I check out? Provide an existing branch name, or a new branch name to create."

---

### Step 6 — Write to the Docs Repo

```bash
cd {provided-docs-path}
git checkout {branch}
# If branch doesn't exist: git checkout -b {branch}
```

Then create and write all files listed in the checklist below.

---

### Step 7 — Capture and Upload Documentation Screenshots

After writing all documentation files, identify all required screenshots by reviewing the webapp implementation you read in Step 2.

**Standard Screenshots (common to most integrations):**

1. `doc_sendtodcc.webp` - DCC Bridge dropdown menu
2. `doc_sendto{plugin}.webp` - Send to {Platform} menu item (highlighted)
3. `doc-moredcc.webp` - More DCC options panel (shared, already exist on cdn)
4. `doc-community.webp` - Community models with DCC Bridge (shared, already exist on cdn)

**Integration-Specific Screenshots (identify from webapp dialogs):**

Based on the dialog components you read in Step 2, identify and list additional screenshots needed:

- For **OAuth integrations**: Connect dialog, upload progress, success dialog
  - `doc_{plugin}_connect.webp` - Connect dialog
  - `doc_{plugin}_upload.webp` - Upload progress dialog
  - `doc_{plugin}_success.webp` - Success dialog with result

- For **URL scheme integrations** (e.g., 3D printing): Export confirmation, settings dialog
  - `doc_{plugin}_export.webp` - Export confirmation dialog
  - `doc_{plugin}_settings.webp` - Settings/configuration screen (if applicable)

- For **other platform-specific dialogs**: Any additional confirmation, error, or status screens shown in the workflow

**Present the complete screenshot list to the user**, including both standard and integration-specific screenshots, before asking them to capture.

**Capture Tips:**
- Save as PNG first, then convert to WebP format

**Upload to CDN:**

Upload screenshots via https://cdn.meshy.team/ to the path:
`docs-assets/{plugin}-plugin/v1.0/`

**After Upload:**

Remove all `{/* TODO: upload screenshot */}` comments from the MDX files and verify all image URLs are accessible.

---

## Docs Repo File Checklist

For each new DCC plugin, create the following in `meshy-docs/src/app/[locale]/{plugin}-plugin/`:

### Files to Create (one set per page)

```
{plugin}-plugin/{page}/
├── en.mdx        ← full English content
├── zh.mdx        ← Chinese content, or TODO placeholder (see template below)
└── page.tsx      ← locale loader + metadata (see template below)
```

### Files to Update

```
src/utils/navigation.ts     ← add a new NavGroup for this plugin
src/messages/en.json        ← add {Plugin}Plugin metadata keys
src/messages/zh.json        ← add same keys in Chinese (or copy EN as placeholder)
```

---

## MDX Format Reference

### Every `.mdx` File Structure

```mdx
import { HeroPattern } from "@/components/shared/HeroPattern"

export const sections = [
  { title: "Section Title", id: "section-id" },
  { title: "Another Section", id: "another-section" },
]

<HeroPattern />

# Page Title

Lead paragraph that describes the page in one or two sentences. {{ className: 'lead' }}

---

## Section Title

Content here.

---

## Another Section

Content here.
```

Rules:
- `import { HeroPattern }` is always the first line
- `export const sections` lists every H2 — the `id` is the kebab-case version of the title
- `<HeroPattern />` comes immediately after the exports, before H1
- Lead paragraph after H1 always ends with `{{ className: 'lead' }}`
- `---` divider separates every H2 section
- Always add a blank line between paragraphs

---

### `page.tsx` — Same for Every Page (only the i18n key changes)

```tsx
import { getMetadata } from "@/utils/metadata"
import { notFound } from "next/navigation"

export default async function Page({ params }: { params: { locale: string } }) {
  const { locale } = params
  try {
    const Content = (await import(`./${locale}.mdx`)).default
    return <Content />
  } catch {
    notFound()
  }
}

export function generateMetadata() {
  return getMetadata((t) => ({
    title: t("{Plugin}Plugin.{Page}.Title"),
    description: t("{Plugin}Plugin.{Page}.Description"),
  }))
}
```

Key naming pattern for i18n keys: `{Plugin}Plugin.{Page}.Title / Description`
- `{Plugin}` = PascalCase platform name, e.g., `Roblox`, `Unity`, `Blender`
- `{Page}` = PascalCase page identifier, e.g., `Introduction`, `BridgeTo{Tool}`, `AnimatedModels`

---

### `zh.mdx` — Placeholder When Translation Is Not Ready

```mdx
{/* zh: TODO — translate from introduction.en.mdx */}
```

---

## Content Templates

### Introduction Page

Standard sections: Prerequisite → Installation → (Plugin Features or Getting Started)

**Lead paragraph format**: Use the pattern "This is the official documentation of Meshy {Tool} [plugin/bridge], you'll find detailed instructions on how to [main purpose]."

**Note format**:
- Title: "Welcome to the Meshy {Tool} [Plugin/Bridge] Documentation!"
- Body: "In this guide, we will walk you through how to efficiently use this [plugin/bridge]. The documentation covers:"
- List pages with descriptions using bullet points
- End with "Let's get started! 🚀"

```mdx
import { HeroPattern } from "@/components/shared/HeroPattern"

export const sections = [
  { title: "Prerequisite", id: "prerequisite" },
  { title: "Installation", id: "installation" },
  { title: "Plugin Features", id: "plugin-features" },
]

<HeroPattern />

# Meshy for {Tool}

This is the official documentation of Meshy {Tool} [plugin/bridge], you'll find detailed instructions on how to [main purpose]. {{ className: 'lead' }}

---

<Note>
<span className="font-bold text-inherit">Welcome to the Meshy {Tool} [Plugin/Bridge] Documentation!</span>

In this guide, we will walk you through how to efficiently use this [plugin/bridge]. The documentation covers:

- **[Introduction](/{plugin}-plugin/introduction)** – Learn about installation and requirements
- **[Bridge to {Tool}](/{plugin}-plugin/bridge-to-{plugin})** – Learn how to send models from Meshy to {Tool} with one click

Let's get started! 🚀
</Note>

## Prerequisite

<span className="font-bold text-inherit">Meshy {Tool} Plugin</span> enables seamless import of
<span className="font-bold text-inherit">MeshyAI-generated models</span> into {Tool}.

To use it, you need:

- {List requirements: account type, software version, download steps}

ATTENTION: We have tested the following {Tool} versions: `{version}`

## Installation

{Step-by-step installation instructions derived from the README and webapp download flow.}

## Plugin Features {{ id: "plugin-features" }}

{List and describe the main features, with links to their dedicated pages.}
```

---

### Standard Bridge Page (Type 2 — local plugin, no cloud auth)

Standard sections: Run Bridge → Sending Models

```mdx
import { HeroPattern } from "@/components/shared/HeroPattern"

export const sections = [
  { title: "Run Bridge in Meshy-{Tool} Plugin", id: "run-bridge-in-meshy-{plugin}-plugin" },
  { title: "Sending Models to {Tool}", id: "sending-models-to-{plugin}" },
]

<HeroPattern />

# Bridge to {Tool}

Learn how to send Meshy 3D models directly into your {Tool} scene with one click. {{ className: 'lead' }}

---

<Note>
Meshy now supports {Tool} bridging directly from the workspace. Pro members and above can
send models to {Tool} following the steps below.
</Note>

## Run Bridge in Meshy-{Tool} Plugin

{Instructions for starting the bridge inside the plugin — e.g., clicking "Run Bridge".}

   <img src="https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc_{plugin}_panel.webp"
     alt="{Tool}-plugin-panel" style={{width: "500px", height: "auto"}} /> <!-- TODO: upload screenshot -->

## Sending Models to {Tool}

Navigate to the model you want in your <span className="font-bold text-inherit">MeshyAI workspace</span>,
click the <span className="font-bold text-inherit">DCC Bridge</span> menu, and select
<span className="font-bold text-inherit">Send to {Tool}</span>.

   ![Meshy-SendToDCC](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc_sendtodcc.webp) <!-- TODO: upload screenshot -->

   ![SendTo{Tool}](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc_sendto{plugin}.webp) <!-- TODO: upload screenshot -->

The model will be automatically downloaded and imported directly into your {Tool} scene.

Any 3D model you generate in your workspace can be effortlessly imported into
<span className="font-bold text-inherit">{Tool}</span> via the
<span className="font-bold text-inherit">DCC Bridge</span>.

   ![MoreDCC](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc-moredcc.webp) <!-- TODO: upload screenshot -->

Likewise, models from the <span className="font-bold text-inherit">MeshyAI community</span> are
fully supported and can also be imported into {Tool} using the DCC Bridge.

   ![Meshy-Community](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc-community.webp) <!-- TODO: upload screenshot -->
```

---

### OAuth-Based Bridge Page (Type 2 + OAuth — cloud platform auth required)

Use this template when the bridge requires the user to authorize with a third-party cloud platform before uploading. Derive the exact section titles and content from the webapp's dialog components and the plugin's auth flow.

**IMPORTANT**: Do NOT include a "Download and Install the Bridge" section in the bridge page. Installation is covered in the Introduction page. The bridge page should start directly with connecting the account.

Standard sections: Connect Account → Send Model → Find Asset in Platform → Troubleshooting

**Lead paragraph format**: Use the pattern "Learn how to use the Meshy {Tool} Bridge to [main action] with one click."

**Note format**:
- First note: Reference the introduction page for installation: "Before you begin, make sure you have downloaded and installed the Meshy {Tool} Bridge. For detailed instructions, please refer to the [Introduction](/{plugin}-plugin/introduction) section."
- Second note: "Meshy now supports {Tool} bridging directly from the workspace. Pro members and above can send models to {Tool} following the steps below."

```mdx
import { HeroPattern } from "@/components/shared/HeroPattern"

export const sections = [
  { title: "Connect Your {Platform} Account", id: "connect-your-{platform}-account" },
  { title: "Sending Models to {Platform}", id: "sending-models-to-{platform}" },
  { title: "Finding Your Model in {Platform}", id: "finding-your-model-in-{platform}" },
  { title: "Troubleshooting", id: "troubleshooting" },
]

<HeroPattern />

# Bridge to {Tool}

Learn how to use the Meshy {Tool} Bridge to [main action] with one click. {{ className: 'lead' }}

---

<Note>
Before you begin, make sure you have downloaded and installed the Meshy {Tool} Bridge. For detailed instructions, please refer to the [Introduction](/{plugin}-plugin/introduction) section.
</Note>

<Note>
Meshy now supports {Tool} bridging directly from the workspace. Pro members and above can
send models to {Tool} following the steps below.
</Note>

## Connect Your {Platform} Account

In the <span className="font-bold text-inherit">MeshyAI workspace</span>, click the
<span className="font-bold text-inherit">DCC Bridge</span> menu and select
<span className="font-bold text-inherit">Send to {Tool}</span>.

   ![Meshy-SendToDCC](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc_sendtodcc.webp) <!-- TODO: upload screenshot -->

If this is your first time, the <span className="font-bold text-inherit">Connect to {Platform}</span>
dialog will appear. Click <span className="font-bold text-inherit">Connect with {Platform}</span>
to open an authorization popup.

   ![{Platform}-ConnectDialog](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc_{plugin}_connect.webp) <!-- TODO: upload screenshot -->

{Describe what permissions are requested and how to approve. Derived from ConnectDialog component.}

## Sending Models to {Platform}

After connecting, navigate to the model you want in your
<span className="font-bold text-inherit">MeshyAI workspace</span> and click
<span className="font-bold text-inherit">Send to {Tool}</span> from the DCC Bridge menu.

   ![SendTo{Tool}](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc_sendto{plugin}.webp) <!-- TODO: upload screenshot -->

{Describe the upload dialog and progress states — derived from UploadDialog component.}

{Describe the success dialog — derived from SuccessDialog component.}

Any 3D model you generate in your workspace can be sent to {Platform} via the
<span className="font-bold text-inherit">DCC Bridge</span>.

   ![MoreDCC](https://cdn.meshy.ai/docs-assets/{plugin}-plugin/v1.0/doc-moredcc.webp) <!-- TODO: upload screenshot -->

## Finding Your Model in {Platform}

{Explain where the asset appears after upload and how to use it — derived from SuccessDialog instructions and platform documentation.}

## Troubleshooting

| Issue | Cause | Solution |
| ----- | ----- | -------- |
| {Error message from webapp} | {Root cause} | {How to fix} |
| {Error message from webapp} | {Root cause} | {How to fix} |

{Derive error rows from the webapp's error handling code and the plugin's API error responses.}
```

---

## MDX Components Reference

| Component | Syntax | When to use |
|-----------|--------|-------------|
| `<HeroPattern />` | `<HeroPattern />` | Always first, after imports — every page |
| `<Note>` | `<Note>content</Note>` | Callout boxes: tips, prerequisites, warnings |
| `<ExternalLink>` | `<ExternalLink href="...">text</ExternalLink>` | Links that open in a new tab |
| Standard image | `![alt](url)` | Full-width images |
| Sized image | `<img src="..." style={{width:"500px",height:"auto"}} />` | Fixed-width images |
| Two-column | `<Row><Col>...</Col><Col>...</Col></Row>` | Side-by-side layout |
| Video | `<YouTube id="..." title="..." caption="..." />` | Embedded YouTube video |
| Bold UI label | `<span className="font-bold text-inherit">text</span>` | Highlight button/menu names inline |

---

## Writing Style Rules

Source: Meshy internal writing guide (`meshy-docs/src/app/[locale]/internal/writing-guide/en.mdx`).

- **Language**: simple and concise; avoid jargon
- **Voice**: active ("click the button", not "the button should be clicked")
- **Tense**: present tense
- **Person**: second person — address the reader as "you"
- **Headings**: Title Case for all H1, H2, H3
- **Heading levels**: max 3 levels. Use `**bold**` instead of H4
- **After H1**: always add a lead paragraph ending with `{{ className: 'lead' }}`
- **Between H2 sections**: always add `---`
- **Between paragraphs**: always add a blank line

---

## CDN Image Convention

All docs images are hosted on Meshy's CDN:

```
https://cdn.meshy.ai/docs-assets/{plugin-name}/{version-folder}/{filename}.webp
```

- Use `{plugin}-plugin/v1.0/` as the base path for a new plugin's first version
- Use descriptive filenames: `doc_sendtodcc.webp`, `doc_{plugin}_connect.webp`, `doc_{plugin}_success.webp`, etc.
- Mark every image placeholder with `{/* TODO: upload screenshot */}` — real screenshots will be uploaded to CDN separately
- **IMPORTANT**: Use MDX comment syntax `{/* comment */}` instead of HTML comments `<!-- comment -->` in MDX files

**Shared images** (reuse from any existing plugin path when the UI is visually identical):
- DCC Bridge dropdown menu: `doc_sendtodcc.webp`
- More DCC options panel: `doc-moredcc.webp`
- Community models import: `doc-community.webp`

---

## i18n Key Conventions

### `src/messages/en.json` and `zh.json` — add under top level

```json
"{Plugin}Plugin": {
  "Introduction": {
    "Title": "Meshy for {Tool}",
    "Description": "{One sentence describing the plugin/bridge for SEO.}"
  },
  "BridgeTo{Tool}": {
    "Title": "Bridge to {Tool} - Meshy Docs",
    "Description": "{One sentence describing the bridge page for SEO.}"
  },
  "AnimatedModels": {
    "Title": "Animated Models - Meshy for {Tool}",
    "Description": "Learn how to import and work with animated models in {Tool} using the Meshy plugin."
  },
  "Troubleshooting": {
    "Title": "Troubleshooting - {Tool} Plugin",
    "Description": "Find solutions to common issues you might encounter while using the Meshy {Tool} plugin."
  }
}
```

Include only the keys for pages that actually exist. For `zh.json`, provide Chinese translations or copy the English as a placeholder.

### Navigation i18n keys — add under `Navigation.Sidebar` in both locale files

```json
"Navigation.Sidebar.{Plugin}Plugin": {
  "Title": "{Tool}",
  "Introduction": "Introduction",
  "BridgeTo{Tool}": "Bridge to {Tool}",
  "AnimatedModels": "Animated Models",
  "Troubleshooting": "Troubleshooting"
}
```

---

## Navigation Registration

In `src/utils/navigation.ts`, add a new NavGroup following the existing plugin pattern:

```ts
{
  title: safeT("Navigation.Sidebar.{Plugin}Plugin.Title", "{Tool}"),
  links: [
    {
      title: safeT("Navigation.Sidebar.{Plugin}Plugin.Introduction", "Introduction"),
      href: "/{plugin}-plugin/introduction",
    },
    {
      title: safeT("Navigation.Sidebar.{Plugin}Plugin.BridgeTo{Tool}", "Bridge to {Tool}"),
      href: "/{plugin}-plugin/bridge-to-{plugin}",
    },
    // Add AnimatedModels, Troubleshooting, etc. only if those pages exist
  ],
},
```

Place the new NavGroup near other game engine or DCC tool plugins for logical grouping.

---

## Reference Examples

When in doubt about tone, structure, or formatting, read these existing docs in the meshy-docs repo:

| What to learn | File path in meshy-docs |
|---------------|------------------------|
| Clean minimal bridge page | `src/app/[locale]/unity-plugin/bridge-to-unity/en.mdx` |
| Rich introduction with feature list | `src/app/[locale]/blender-plugin/introduction/en.mdx` |
| Troubleshooting table format | `src/app/[locale]/unreal-plugin/troubleshooting/en.mdx` |
| Simple introduction (game engine pattern) | `src/app/[locale]/godot-plugin/introduction/en.mdx` |
| Writing style rules (internal) | `src/app/[locale]/internal/writing-guide/en.mdx` |

---

## Integration Type Reference

| Type | Description | Example integrations | Key doc differences |
|------|-------------|---------------------|---------------------|
| **Type 1** | Pure webapp — URL scheme launches the 3rd-party app directly, no local server | 3D printing slicers (Bambu Studio, OrcaSlicer, Creality Print) | No "run a plugin" step; document as "click Export → app opens automatically" |
| **Type 2** | Webapp + local bridge/plugin running on user's machine via localhost | Blender, Unity, Godot, Unreal, Maya, 3ds Max | Document: download plugin → install → run bridge → send from Meshy workspace |
| **Type 2 + OAuth** | Type 2 with additional cloud platform authentication before upload | Roblox Bridge | Additionally document: OAuth connect dialog, upload polling, finding the asset in the platform's inventory |
