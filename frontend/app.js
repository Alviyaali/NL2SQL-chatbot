// ==============================================================
// NL2SQL Clinic Chatbot - Frontend Logic
// ==============================================================

const API_BASE = window.location.origin;
const STORAGE_KEY = "nl2sql_conversations";
const MAX_CONVERSATIONS = 50;

// --- DOM References ---
const sidebar = document.getElementById("sidebar");
const chatHistory = document.getElementById("chatHistory");
const newChatBtn = document.getElementById("newChatBtn");
const clearAllBtn = document.getElementById("clearAllBtn");
const logoutBtn = document.getElementById("logoutBtn");
const menuBtn = document.getElementById("menuBtn");
const messagesEl = document.getElementById("messages");
const welcomeEl = document.getElementById("welcome");
const inputForm = document.getElementById("inputForm");
const questionInput = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");

// --- State ---
let conversations = [];
let activeConvId = null;
let isLoading = false;

// ==============================================================
// INITIALIZATION
// ==============================================================


function init() {
    // Check authentication and redirect if not logged in
    SessionManager.requireAuth();
    
    loadConversations();
    renderUserProfile();
    renderSidebar();

    // Restore last active conversation, or show welcome
    if (conversations.length > 0) {
        const lastId = localStorage.getItem("nl2sql_active_id");
        const target = conversations.find((c) => c.id === lastId) || conversations[0];
        switchConversation(target.id);
    } else {
        showWelcome();
    }

    // Event listeners
    newChatBtn.addEventListener("click", startNewChat);
    clearAllBtn.addEventListener("click", clearAllChats);
    logoutBtn.addEventListener("click", SessionManager.logout);
    menuBtn.addEventListener("click", () => sidebar.classList.toggle("open"));
    inputForm.addEventListener("submit", handleSubmit);
    questionInput.addEventListener("input", autoResize);
    questionInput.addEventListener("keydown", handleKeydown);
}

// ==============================================================
// USER PROFILE DISPLAY
// ==============================================================

/**
 * Render user profile information in the chat header.
 * Replaces the existing header-badge with user's name.
 */
function renderUserProfile() {
    const user = SessionManager.getUser();
    const headerBadge = document.querySelector('.header-badge');
    
    if (headerBadge && user.name) {
        headerBadge.textContent = user.name;
        headerBadge.title = user.email;
    }
}

// ================================================================
// CONVERSATIONS — localStorage CRUD
// ================================================================

function loadConversations() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        conversations = raw ? JSON.parse(raw) : [];
    } catch {
        conversations = [];
    }
}

function saveConversations() {
    // Evict oldest if over limit
    while (conversations.length > MAX_CONVERSATIONS) {
        conversations.pop();
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    if (activeConvId) {
        localStorage.setItem("nl2sql_active_id", activeConvId);
    }
}

function createConversation() {
    const conv = {
        id: "conv-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8),
        title: "New Chat",
        createdAt: Date.now(),
        messages: [],
    };

    conversations.unshift(conv);
    saveConversations();
    return conv;
}

function deleteConversation(convId) {
    conversations = conversations.filter((c) => c.id !== convId);
    saveConversations();

    if (activeConvId === convId) {
        if (conversations.length > 0) {
            switchConversation(conversations[0].id);
        } else {
            activeConvId = null;
            showWelcome();
        }
    }

    renderSidebar();
}

function clearAllChats() {
    if (!confirm("Delete all chat history?")) return;
    conversations = [];
    activeConvId = null;
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem("nl2sql_active_id");
    renderSidebar();
    showWelcome();
}

// ================================================================
// SIDEBAR RENDERING
// ================================================================

function renderSidebar() {
    chatHistory.innerHTML = "";
    conversations.forEach((conv) => {
        const item = document.createElement("div");
        item.className = "chat-history-item" + (conv.id === activeConvId ? " active" : "");
        item.innerHTML = `
            <span class="item-icon">💬</span>
            <span class="item-title">${escapeHtml(conv.title)}</span>
            <button class="delete-btn" title="Delete chat">&times;</button>
        `;

        item.querySelector(".item-title").addEventListener("click", () => switchConversation(conv.id));
        item.querySelector(".item-icon").addEventListener("click", () => switchConversation(conv.id));
        item.querySelector(".delete-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            deleteConversation(conv.id);
        });

        chatHistory.appendChild(item);
    });
}

// ================================================================
// CONVERSATION SWITCHING
// ================================================================

function switchConversation(convId) {
    activeConvId = convId;
    localStorage.setItem("nl2sql_active_id", convId);
    renderSidebar();
    renderMessages();
    sidebar.classList.remove("open");
}

function startNewChat() {
    const conv = createConversation();
    switchConversation(conv.id);
}

/**
 * Attach click event handlers to all suggestion buttons within a container.
 * Centralizes event handler attachment to ensure dynamically created buttons work.
 * @param {HTMLElement} container - The container element with suggestion buttons
 */
function attachSuggestionHandlers(container) {
    container.querySelectorAll(".suggestion").forEach((btn) => {
        btn.addEventListener("click", () => {
            questionInput.value = btn.dataset.q;
            questionInput.focus();
            inputForm.dispatchEvent(new Event("submit"));
        });
    });
}

function showWelcome() {
    messagesEl.innerHTML = "";
    messagesEl.appendChild(createWelcomeEl());
}

function createWelcomeEl() {
    const user = SessionManager.getUser();
    const div = document.createElement("div");
    div.className = "welcome";
    div.innerHTML = `
        <p class="greeting">Hi ${escapeHtml(user.name)}, how can I help you?</p>
        <h1>🩺 Clinic Chatbot</h1>
        <p>Ask anything about your clinic data — patients, doctors, appointments, treatments, invoices.</p>
        <div class="suggestions">
            <button class="suggestion" data-q="How many patients do we have?">How many patients do we have?</button>
            <button class="suggestion" data-q="Which doctor has the most appointments?">Which doctor has the most appointments?</button>
            <button class="suggestion" data-q="Show revenue trend by month">Show revenue trend by month</button>
            <button class="suggestion" data-q="List all doctors and their specializations">List all doctors and their specializations</button>
        </div>
    `;

    // Attach event handlers to dynamically created suggestion buttons
    attachSuggestionHandlers(div);

    return div;
}

// ================================================================
// MESSAGE RENDERING
// ================================================================

function renderMessages() {
    const conv = conversations.find((c) => c.id === activeConvId);
    messagesEl.innerHTML = "";

    if (!conv || conv.messages.length === 0) {
        messagesEl.appendChild(createWelcomeEl());
        return;
    }

    conv.messages.forEach((msg, idx) => {
        const wrapper = document.createElement("div");
        wrapper.className = "message-wrapper";
        
        if (msg.role === "user") {
            wrapper.appendChild(createUserBubble(msg.content));
        } else {
            wrapper.appendChild(createBotBubble(msg.response, idx));
        }
        
        messagesEl.appendChild(wrapper);
    });

    scrollToBottom();

    // Re-render any Plotly charts (they can't survive innerHTML serialization)
    requestAnimationFrame(() => renderAllCharts(conv));
}

function createUserBubble(text) {
    const div = document.createElement("div");
    div.className = "message user";
    div.innerHTML = `
        <div class="avatar">U</div>
        <div class="bubble">${escapeHtml(text)}</div>
    `;
    return div;
}

function createBotBubble(response, index) {
    const div = document.createElement("div");
    const isError = response.error;
    div.className = "message " + (isError ? "error" : "bot");

    let html = `<div class="avatar">${isError ? "⚠" : "G"}</div><div class="bubble">`;

    // 1. Prose answer (cleaned)
    if (response.message) {
        const cleanedMessage = cleanResponseMessage(response.message);
        if (cleanedMessage) {
            html += `<div class="response-text">${formatMessage(cleanedMessage)}</div>`;
        }
    }

    if (!isError) {
        // 2. SQL query
        if (response.sql_query) {
            html += `
                <details class="sql-section">
                    <summary>📄 View SQL Query</summary>
                    <pre class="sql-code">${escapeHtml(response.sql_query)}</pre>
                </details>
            `;
        }

        // 3. Data table
        if (response.columns && response.columns.length > 0 && response.rows && response.rows.length > 0) {
            html += buildTableHtml(response.columns, response.rows, response.row_count);
        }

        // 4. Chart placeholder
        if (response.chart) {
            html += `<div class="chart-section" id="chart-${index}"></div>`;
        }
    }

    html += `</div>`;
    div.innerHTML = html;
    return div;
}

function buildTableHtml(columns, rows, rowCount) {
    let html = `<div class="table-section">`;
    html += `<div class="table-header">📊 Results (${rowCount} row${rowCount !== 1 ? "s" : ""})</div>`;
    html += `<div class="table-wrapper"><table class="data-table">`;

    // Header
    html += "<thead><tr>";
    columns.forEach((col) => {
        html += `<th>${escapeHtml(col)}</th>`;
    });
    html += "</tr></thead>";

    // Body
    html += "<tbody>";
    rows.forEach((row) => {
        html += "<tr>";
        row.forEach((cell) => {
            const val = cell === null ? "—" : String(cell);
            html += `<td>${escapeHtml(val)}</td>`;
        });
        html += "</tr>";
    });
    html += "</tbody></table></div></div>";
    return html;
}

function renderAllCharts(conv) {
    conv.messages.forEach((msg, idx) => {
        if (msg.role === "bot" && msg.response.chart) {
            renderChart(msg.response.chart, idx);
        }
    });
}

function renderChart(chart, index) {
    const el = document.getElementById(`chart-${index}`);
    if (!el || typeof Plotly === "undefined") return;

    try {
        // Strip the large template to keep it lean; Plotly uses defaults
        const layout = Object.assign({}, chart.layout || {});
        if (layout.template) delete layout.template;
        layout.autosize = true;
        layout.margin = layout.margin || { l: 40, r: 20, t: 50, b: 40 };

        Plotly.newPlot(el, chart.data, layout, {
            responsive: true,
            displayModeBar: false,
        });
    } catch (err) {
        console.error("Chart render error:", err);
        el.innerHTML = '<p style="padding:12px;color:#888;">Could not render chart.</p>';
    }
}

// ============================================================
// FORMAT HELPERS
// ============================================================

/**
 * Clean the response message to remove technical details and internal instructions
 * @param {string} text - Raw message from backend
 * @returns {string} - Cleaned user-friendly message
 */
function cleanResponseMessage(text) {
    if (!text) return "";
    
    // Remove everything before and including "SQL Query:" or similar patterns
    text = text.replace(/^[\s\S]*?(?:SQL Query:|Generated SQL:|Query:)\s*```[\s\S]*?```\s*/i, "");
    
    // Remove IMPORTANT instructions about filenames
    text = text.replace(/IMPORTANT:.*?(?:USE FILENAME|filename).*?\.csv/gi, "");
    
    // Remove technical error messages and stack traces
    text = text.replace(/Error:.*?(?:\n|$)/gi, "");
    text = text.replace(/Traceback.*?(?:\n|$)/gi, "");
    
    // Remove SQL code blocks that might still be present
    text = text.replace(/```sql[\s\S]*?```/gi, "");
    text = text.replace(/```[\s\S]*?```/gi, "");
    
    // Remove lines that start with technical markers
    text = text.split('\n')
        .filter(line => {
            const trimmed = line.trim().toLowerCase();
            return !trimmed.startsWith('important:') &&
                   !trimmed.startsWith('note:') &&
                   !trimmed.startsWith('debug:') &&
                   !trimmed.startsWith('error:') &&
                   !trimmed.includes('filename:') &&
                   !trimmed.includes('query_results_');
        })
        .join('\n');
    
    // Clean up excessive whitespace
    text = text.replace(/\n{3,}/g, "\n\n").trim();
    
    return text;
}

function formatMessage(text) {
    // Clean up duplicated agent prose (known backend duplication)
    text = deduplicateText(text);

    // Convert markdown-ish bold
    text = escapeHtml(text);
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\n/g, "<br>");
    return text;
}

function deduplicateText(text) {
    // The backend sometimes repeats the same summary 2-3 times.
    // Split on double newlines and remove duplicate paragraphs.
    const parts = text.split(/\n{2,}/);
    const seen = new Set();
    const unique = [];
    for (const part of parts) {
        const key = part.trim().toLowerCase();
        if (key && !seen.has(key)) {
            seen.add(key);
            unique.push(part);
        }
    }
    return unique.join("\n\n");
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    });
}

// ============================================================
// SEND / RECEIVE
// ============================================================

async function handleSubmit(e) {
    e.preventDefault();
    const question = questionInput.value.trim();
    if (!question || isLoading) return;

    // Ensure we have an active conversation
    if (!activeConvId) {
        const conv = createConversation();
        activeConvId = conv.id;
    }

    const conv = conversations.find((c) => c.id === activeConvId);
    if (!conv) return;

    // Update title from first question
    if (conv.messages.length === 0) {
        conv.title = question.length > 35 ? question.slice(0, 35) + "..." : question;
        renderSidebar();
    }

    // Add user message
    conv.messages.push({ role: "user", content: question });
    saveConversations();

    // Clear input
    questionInput.value = "";
    autoResize();

    // Hide welcome, show user bubble
    clearWelcome();
    const userWrapper = document.createElement("div");
    userWrapper.className = "message-wrapper";
    userWrapper.appendChild(createUserBubble(question));
    messagesEl.appendChild(userWrapper);
    scrollToBottom();

    // Show typing indicator
    const typingWrapper = document.createElement("div");
    typingWrapper.className = "message-wrapper";
    const typingEl = createTypingIndicator();
    typingWrapper.appendChild(typingEl);
    messagesEl.appendChild(typingWrapper);
    scrollToBottom();

    // Disable input
    setLoading(true);

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });

        const data = await res.json();

        // Store the response (strip chart template to save localStorage space)
        const storable = prepareForStorage(data);
        conv.messages.push({ role: "bot", response: storable });
        saveConversations();

        // Remove typing, render bot bubble
        typingWrapper.remove();
        const botIdx = conv.messages.length - 1;
        const botWrapper = document.createElement("div");
        botWrapper.className = "message-wrapper";
        botWrapper.appendChild(createBotBubble(storable, botIdx));
        messagesEl.appendChild(botWrapper);
        scrollToBottom();

        // Render chart if present
        if (data.chart) {
            renderChart(data.chart, botIdx);
        }
    } catch (err) {
        typingWrapper.remove();
        const errorResp = {
            error: true,
            message: "Network error — could not reach the server. Is it running?",
            sql_query: null,
            columns: [],
            rows: [],
            row_count: 0,
            chart: null,
            chart_type: null,
        };
        conv.messages.push({ role: "bot", response: errorResp });
        saveConversations();
        const errorWrapper = document.createElement("div");
        errorWrapper.className = "message-wrapper";
        errorWrapper.appendChild(createBotBubble(errorResp, conv.messages.length - 1));
        messagesEl.appendChild(errorWrapper);
        scrollToBottom();
    } finally {
        setLoading(false);
    }
}

function prepareForStorage(data) {
    // Deep-copy and strip the heavy Plotly template to keep localStorage lean
    const copy = JSON.parse(JSON.stringify(data));
    if (copy.chart && copy.chart.layout && copy.chart.layout.template) {
        delete copy.chart.layout.template;
    }
    return copy;
}

function createTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message bot";
    div.innerHTML = `
    <div class="avatar">G</div>
    <div class="bubble">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
    return div;
}

function clearWelcome() {
    const w = messagesEl.querySelector(".welcome");
    if (w) w.remove();
}

function setLoading(state) {
    isLoading = state;
    sendBtn.disabled = state;
    questionInput.disabled = state;
    if (!state) questionInput.focus();
}

// ============================================================
// TEXTAREA AUTO-RESIZE
// ============================================================

function autoResize() {
    questionInput.style.height = "auto";
    questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
}

function handleKeydown(e) {
    // Enter to send, Shift+Enter for newline
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        inputForm.dispatchEvent(new Event("submit"));
    }
}

// ============================================================
// BOOT
// ============================================================

document.addEventListener("DOMContentLoaded", init);