# ChatGPT UI — Complete CSS & Styling Reference
> A practical reference for recreating ChatGPT's look in a plain HTML + CSS + JS page.

---

## 1. Color Palette

ChatGPT uses a **dark theme by default** (as of 2024–2025). All values below are the dark-mode defaults.

```css
:root {
  /* Backgrounds */
  --bg-primary:     #212121;   /* Main chat area background */
  --bg-sidebar:     #171717;   /* Left sidebar */
  --bg-input:       #2f2f2f;   /* Message input box */
  --bg-hover:       #2a2a2a;   /* Hover state on sidebar items */
  --bg-active:      #3d3d3d;   /* Active/selected sidebar item */
  --bg-code:        #1a1a1a;   /* Code block background */
  --bg-user-bubble: #2f2f2f;   /* User message bubble */

  /* Text */
  --text-primary:   #ececec;   /* Main body text */
  --text-secondary: #8e8ea0;   /* Muted labels, timestamps, placeholders */
  --text-disabled:  #565869;   /* Disabled/inactive text */
  --text-on-dark:   #ffffff;   /* High-contrast white text */

  /* Borders & Dividers */
  --border-color:   #3d3d3d;   /* Subtle borders (input box, dividers) */
  --border-light:   #4a4a4a;   /* Slightly lighter border */

  /* Accent */
  --accent-green:   #19c37d;   /* Send button, links, highlights */
  --accent-hover:   #1aab6d;   /* Hover on green accent */

  /* Scrollbar */
  --scrollbar-thumb: #555;
  --scrollbar-track: transparent;
}
```

**Light mode** (if toggled):
```css
:root[data-theme="light"] {
  --bg-primary:     #ffffff;
  --bg-sidebar:     #f9f9f9;
  --bg-input:       #f4f4f4;
  --bg-user-bubble: #f4f4f4;
  --text-primary:   #0d0d0d;
  --text-secondary: #6e6e80;
  --border-color:   #e5e5e5;
}
```

---

## 2. Typography

### Font Family

ChatGPT uses **Söhne** (a custom typeface by Klim Type Foundry), but it falls back gracefully to system UI fonts. For a faithful recreation without licensing Söhne:

```css
body {
  font-family:
    "Söhne",
    ui-sans-serif,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Helvetica,
    Arial,
    sans-serif;
}

code, pre {
  font-family:
    "Söhne Mono",
    "SFMono-Regular",
    Consolas,
    "Liberation Mono",
    Menlo,
    Courier,
    monospace;
}
```

> **Best free alternative:** Use `"Inter"` from Google Fonts — it's the closest open-source match to Söhne in weight and spacing feel.

### Font Sizes

```css
/* Base */
body           { font-size: 16px; }          /* 1rem */

/* Chat messages */
.message-text  { font-size: 1rem; }          /* 16px */

/* Code blocks */
pre, code      { font-size: 0.875rem; }      /* 14px */

/* Sidebar nav items */
.nav-item      { font-size: 0.875rem; }      /* 14px */

/* Input placeholder */
textarea       { font-size: 1rem; }          /* 16px */

/* Small labels / timestamps */
.label-sm      { font-size: 0.75rem; }       /* 12px */

/* Model selector / dropdown labels */
.model-label   { font-size: 0.875rem; }      /* 14px */
```

### Font Weights

```css
body           { font-weight: 400; }   /* Normal — all body text */
strong, b      { font-weight: 600; }   /* Semi-bold — for bolded markdown */
.heading       { font-weight: 700; }   /* Bold — h1–h3 inside AI responses */
.nav-item      { font-weight: 400; }   /* Regular — sidebar items */
.btn-primary   { font-weight: 600; }   /* Semi-bold — primary buttons */
```

### Line Height

```css
body           { line-height: 1.75; }   /* Comfortable reading for chat messages */
pre            { line-height: 1.5; }    /* Code blocks — slightly tighter */
.label-sm      { line-height: 1.4; }    /* Small labels */
```

---

## 3. Layout & Structure

ChatGPT's page is a **3-column-like layout** that simplifies to 2 visible zones:

```
┌─────────────┬──────────────────────────────────┐
│  Sidebar    │         Main Content              │
│  (260px)    │  ┌────────────────────────────┐   │
│             │  │      Message Feed          │   │
│             │  │  (scrollable, centered)    │   │
│             │  └────────────────────────────┘   │
│             │  ┌────────────────────────────┐   │
│             │  │      Input Bar             │   │
│             │  └────────────────────────────┘   │
└─────────────┴──────────────────────────────────┘
```

### Root Layout (Flexbox)

```css
html, body {
  height: 100%;
  margin: 0;
  overflow: hidden;
}

.app-shell {
  display: flex;
  height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}
```

### Sidebar

```css
.sidebar {
  width: 260px;
  min-width: 260px;
  background-color: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 2px;
  overflow-y: auto;
  border-right: 1px solid var(--border-color);
}
```

### Main Panel

```css
.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
```

### Message Feed (Scrollable Area)

```css
.message-feed {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
  scroll-behavior: smooth;
}
```

### Message Container Width (Centered Column)

ChatGPT constrains chat width for readability:

```css
.message-wrapper {
  max-width: 48rem;       /* 768px — main content column */
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;        /* Side padding on smaller screens */
}
```

---

## 4. Message Bubbles

### AI (Assistant) Messages

AI messages have **no bubble background** — they render directly on the page background with full-width text.

```css
.message-ai {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  align-items: flex-start;
}

.message-ai .message-content {
  flex: 1;
  font-size: 1rem;
  line-height: 1.75;
  color: var(--text-primary);
}
```

### User Messages

User messages have a **rounded pill/bubble** style:

```css
.message-user {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0;
}

.message-user .message-content {
  background-color: var(--bg-user-bubble);
  border-radius: 18px;
  padding: 12px 18px;
  max-width: 80%;
  font-size: 1rem;
  line-height: 1.6;
  color: var(--text-primary);
}
```

### Avatar / Icon

The ChatGPT logo circle appears beside AI messages:

```css
.avatar {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 50%;
  background-color: #19c37d;   /* Green for GPT */
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: white;
  font-weight: 600;
}
```

---

## 5. Input Bar

The input bar is **pinned to the bottom** and has a rounded, bordered textarea:

```css
.input-bar {
  padding: 12px 16px 20px;
  background-color: var(--bg-primary);
}

.input-bar-inner {
  max-width: 48rem;
  margin: 0 auto;
  position: relative;
}

.input-box {
  width: 100%;
  background-color: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 14px 52px 14px 18px;   /* Right padding leaves room for send button */
  font-size: 1rem;
  font-family: inherit;
  color: var(--text-primary);
  resize: none;
  outline: none;
  min-height: 52px;
  max-height: 200px;
  overflow-y: auto;
  line-height: 1.6;
  box-sizing: border-box;
  transition: border-color 0.15s ease;
}

.input-box::placeholder {
  color: var(--text-secondary);
}

.input-box:focus {
  border-color: var(--border-light);
}
```

### Send Button

```css
.send-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background-color: var(--accent-green);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: background-color 0.15s ease, opacity 0.15s ease;
}

.send-btn:hover  { background-color: var(--accent-hover); }
.send-btn:disabled {
  background-color: var(--bg-active);
  opacity: 0.5;
  cursor: not-allowed;
}
```

---

## 6. Sidebar Items & Navigation

```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background-color 0.1s ease;
}

.nav-item:hover   { background-color: var(--bg-hover); }
.nav-item.active  { background-color: var(--bg-active); }

/* Section label (e.g. "Today", "Yesterday") */
.nav-section-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 12px 10px 4px;
  text-transform: none;
  letter-spacing: 0;
}
```

---

## 7. Code Blocks

ChatGPT renders code blocks with a dark background, monospace font, and a "Copy" button:

```css
pre {
  background-color: var(--bg-code);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 12px 0;
  position: relative;
}

code {
  font-family: "SFMono-Regular", Consolas, Menlo, Courier, monospace;
  font-size: 0.875rem;
}

/* Inline code */
p code {
  background-color: var(--bg-input);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85em;
}

/* Language label + copy button row above code block */
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #1a1a1a;
  border-radius: 8px 8px 0 0;
  padding: 6px 12px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
}
```

---

## 8. Buttons (General)

```css
/* Ghost / Icon buttons */
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.btn-icon:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

/* Solid button (e.g. "New chat", "Sign up") */
.btn-solid {
  background-color: var(--accent-green);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.btn-solid:hover { background-color: var(--accent-hover); }

/* Outline button */
.btn-outline {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.btn-outline:hover { background-color: var(--bg-hover); }
```

---

## 9. Scrollbar Styling

```css
/* Webkit (Chrome, Edge, Safari) */
::-webkit-scrollbar        { width: 6px; }
::-webkit-scrollbar-track  { background: transparent; }
::-webkit-scrollbar-thumb  {
  background-color: var(--scrollbar-thumb);
  border-radius: 10px;
}

/* Firefox */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
}
```

---

## 10. Spacing & Sizing Quick Reference

| Element | Value |
|---|---|
| Sidebar width | `260px` |
| Sidebar padding | `8px` |
| Sidebar item padding | `8px 10px` |
| Sidebar item border-radius | `8px` |
| Sidebar item gap (icon + text) | `10px` |
| Message column max-width | `48rem` (768px) |
| Message column padding (sides) | `24px` |
| Message vertical padding | `12px 0` |
| AI message avatar size | `32px` |
| AI message avatar gap | `16px` |
| User bubble padding | `12px 18px` |
| User bubble border-radius | `18px` |
| User bubble max-width | `80%` |
| Input box border-radius | `16px` |
| Input box padding | `14px 52px 14px 18px` |
| Input box min-height | `52px` |
| Input box max-height | `200px` |
| Send button size | `34px × 34px` |
| Send button border-radius | `50%` |
| Code block border-radius | `8px` |
| Code block padding | `16px` |
| Inline code padding | `2px 6px` |
| Inline code border-radius | `4px` |

---

## 11. Transitions & Animation

ChatGPT uses **very subtle, fast transitions** — nothing flashy:

```css
/* Standard hover transitions */
transition: background-color 0.15s ease;
transition: color 0.15s ease;
transition: opacity 0.15s ease;
transition: border-color 0.15s ease;

/* Sidebar collapse (if implementing toggle) */
.sidebar {
  transition: width 0.25s ease, min-width 0.25s ease;
}

/* AI typing cursor blink */
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--text-primary);
  margin-left: 2px;
  animation: blink 1s step-end infinite;
  vertical-align: text-bottom;
}
```

---

## 12. Minimal Page Skeleton (Boilerplate HTML)

Use this as your starting point:

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ChatGPT Clone</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet" />
  <style>
    /* Paste all CSS variables and styles from this doc here */
    body { font-family: "Inter", ui-sans-serif, sans-serif; }
  </style>
</head>
<body>
  <div class="app-shell">

    <!-- Sidebar -->
    <aside class="sidebar">
      <button class="btn-outline" style="margin-bottom: 8px;">+ New chat</button>
      <div class="nav-section-label">Today</div>
      <a class="nav-item active" href="#">Chat title goes here</a>
      <a class="nav-item" href="#">Another chat</a>
    </aside>

    <!-- Main panel -->
    <main class="main-panel">

      <!-- Message feed -->
      <div class="message-feed">
        <div class="message-wrapper">

          <!-- AI message -->
          <div class="message-ai">
            <div class="avatar">G</div>
            <div class="message-content">Hello! How can I help you today?</div>
          </div>

          <!-- User message -->
          <div class="message-user">
            <div class="message-content">Tell me about CSS.</div>
          </div>

        </div>
      </div>

      <!-- Input bar -->
      <div class="input-bar">
        <div class="input-bar-inner">
          <textarea class="input-box" rows="1" placeholder="Message ChatGPT"></textarea>
          <button class="send-btn">↑</button>
        </div>
      </div>

    </main>
  </div>
</body>
</html>
```

---

## 13. Responsive Behavior

On small screens (mobile), the sidebar **hides** and a hamburger icon shows:

```css
@media (max-width: 768px) {
  .sidebar {
    display: none;        /* Hide sidebar */
  }
  .sidebar.open {
    display: flex;        /* Show when toggled */
    position: fixed;
    top: 0; left: 0;
    height: 100vh;
    z-index: 100;
    width: 260px;
  }
  .message-wrapper {
    padding: 0 16px;      /* Reduce side padding on mobile */
  }
}
```

---

## 14. Icons

ChatGPT uses **custom SVG icons** internally. For a clone, use one of these free sets which match the style closely:

- **Lucide** — `https://lucide.dev` (closest match, same stroke style)
- **Heroicons** — `https://heroicons.com`
- **Tabler Icons** — `https://tabler.io/icons`

Typical icon size used throughout the UI:

```css
.icon {
  width: 16px;
  height: 16px;
  stroke-width: 2;        /* Lucide/Heroicons default */
}

.icon-lg {
  width: 20px;
  height: 20px;
}
```

---

*Reference built from visual inspection of ChatGPT's interface (dark mode, desktop, 2024–2025).*
