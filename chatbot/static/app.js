// Memory Care Companion — front-end chat logic (vanilla JS, SSE streaming).
const $ = (id) => document.getElementById(id);

const state = {
  messages: [],      // {role, content} — source of truth, sent to the server
  config: null,
  streaming: false,
};

marked.setOptions({ breaks: true });

// --- Init -----------------------------------------------------------------
async function init() {
  const res = await fetch("/api/config");
  state.config = await res.json();
  const c = state.config;

  $("disclaimer").innerHTML = marked.parseInline(c.disclaimer || "");

  if (c.rag_on) {
    $("sources-title").textContent = "Cases retrieved";
    renderSources([], true);
  } else {
    $("sources-title").textContent = `Cases (${c.total_cases})`;
    renderSources(c.all_sources || [], false);
  }

  if (!c.has_api_key) {
    addMessage("bot", "The server has no `ANTHROPIC_API_KEY` set. Add it to `.env` and restart.");
  }
}


// --- Rendering ------------------------------------------------------------
function renderSources(sources, ragOn) {
  const ul = $("sources");
  ul.innerHTML = "";
  if (!sources.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = ragOn ? "Ask a question to see which cases were used." : "No analyzed cases yet.";
    ul.appendChild(li);
    return;
  }
  for (const s of sources) {
    const li = document.createElement("li");
    const name = s.year ? `${s.title} (${s.year})` : s.title;
    if (s.url) {
      const a = document.createElement("a");
      a.href = s.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = name;
      li.appendChild(a);
    } else {
      li.appendChild(document.createTextNode(name));
    }
    if (s.score != null) {
      const span = document.createElement("span");
      span.className = "score";
      span.textContent = ` ${s.score.toFixed(2)}`;
      li.appendChild(span);
    }
    ul.appendChild(li);
  }
}

function addMessage(role, content) {
  $("welcome")?.remove();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "bot") renderMarkdown(bubble, content);
  else bubble.innerHTML = escapeHtml(content);
  wrap.appendChild(bubble);
  $("messages").appendChild(wrap);
  scrollDown();
  return bubble;
}

// Render model markdown, then force every link to open safely in a new tab.
function renderMarkdown(el, md) {
  el.innerHTML = marked.parse(md);
  for (const a of el.querySelectorAll("a[href]")) {
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  }
}

// The cases retrieved for this answer, pinned under it. Built from the
// retrieval result itself, so it stays correct and stays with the answer even
// if the model's prose omits a citation.
//
// Deliberately says "retrieved", not "cited": these are the cases put in front
// of the model, which is a superset of the ones it actually drew on. The
// answer's own inline links show what it really used.
function renderMessageSources(wrap, sources) {
  wrap.querySelector(".msg-sources")?.remove();
  if (!sources || !sources.length) return;

  const box = document.createElement("details");
  box.className = "msg-sources";
  const n = sources.length;
  box.innerHTML =
    `<summary>${n} case${n > 1 ? "s" : ""} retrieved for this answer</summary>`;

  const ul = document.createElement("ul");
  for (const s of sources) {
    const li = document.createElement("li");
    const name = s.year ? `${s.title} (${s.year})` : s.title;
    const a = document.createElement("a");
    if (s.url) {
      a.href = s.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = name;
      li.appendChild(a);
    } else {
      li.textContent = name;
    }
    ul.appendChild(li);
  }
  box.appendChild(ul);
  wrap.appendChild(box);
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function scrollDown() {
  const m = $("messages");
  m.scrollTop = m.scrollHeight;
}

// --- Send / stream --------------------------------------------------------
async function send(text) {
  if (state.streaming || !text.trim()) return;
  state.streaming = true;
  $("send").disabled = true;

  state.messages.push({ role: "user", content: text });
  addMessage("user", text);

  const bubble = addMessage("bot", "");
  bubble.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: state.messages }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      const parts = buf.split("\n\n");
      buf = parts.pop();           // keep incomplete trailing chunk
      for (const part of parts) {
        const line = part.replace(/^data: /, "").trim();
        if (!line) continue;
        handleEvent(JSON.parse(line), bubble);
      }
    }
  } catch (err) {
    renderMarkdown(bubble, `Connection error: ${err.message}`);
  }

  if (bubble._raw) state.messages.push({ role: "assistant", content: bubble._raw });
  state.streaming = false;
  $("send").disabled = false;
}

function handleEvent(evt, bubble) {
  switch (evt.type) {
    case "sources":
      // Per-answer card only under RAG; the fallback "sources" list is all 92 cases.
      if (state.config.rag_on) {
        renderSources(evt.sources, true);
        renderMessageSources(bubble.parentElement, evt.sources);
      }
      break;
    case "delta":
      bubble._raw = (bubble._raw || "") + evt.text;
      renderMarkdown(bubble, bubble._raw);
      scrollDown();
      break;
    case "notice":
      console.warn(evt.message);
      break;
    case "error":
      renderMarkdown(bubble, evt.message);
      break;
  }
}

// --- Events ---------------------------------------------------------------
$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("input");
  const text = input.value;
  input.value = "";
  input.style.height = "auto";
  send(text);
});

$("input").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = Math.min(e.target.scrollHeight, 180) + "px";
});

$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});

$("clear").addEventListener("click", () => {
  state.messages = [];
  $("messages").innerHTML = "";
  if (state.config.rag_on) renderSources([], true);
});

// --- Mobile drawer --------------------------------------------------------
// The open drawer covers the Menu button, so it needs its own ways out:
// the Close button, the scrim, and Escape.
function setDrawer(open) {
  $("sidebar").classList.toggle("open", open);
  $("scrim").hidden = !open;
  $("menu").setAttribute("aria-expanded", String(open));
  document.body.classList.toggle("drawer-open", open);
  if (open) $("drawer-close").focus();
  else $("menu").focus();
}

$("menu").addEventListener("click", () =>
  setDrawer(!$("sidebar").classList.contains("open")));
$("drawer-close").addEventListener("click", () => setDrawer(false));
$("scrim").addEventListener("click", () => setDrawer(false));

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("sidebar").classList.contains("open")) setDrawer(false);
});

// Following a source link should get the drawer out of the way behind it.
$("sources").addEventListener("click", (e) => {
  if (e.target.closest("a")) setDrawer(false);
});

document.querySelectorAll("#suggestions button").forEach((b) =>
  b.addEventListener("click", () => send(b.textContent)));

init();
