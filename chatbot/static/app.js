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
    $("sources-title").textContent = "Cases referenced";
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
    const score = s.score != null ? ` <span class="score">${s.score.toFixed(2)}</span>` : "";
    li.innerHTML = s.url ? `<a href="${s.url}" target="_blank" rel="noopener">${name}</a>${score}`
                         : `${name}${score}`;
    ul.appendChild(li);
  }
}

function addMessage(role, content) {
  $("welcome")?.remove();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "bot" ? marked.parse(content) : escapeHtml(content);
  wrap.appendChild(bubble);
  $("messages").appendChild(wrap);
  scrollDown();
  return bubble;
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
    bubble.innerHTML = marked.parse(`Connection error: ${err.message}`);
  }

  if (bubble._raw) state.messages.push({ role: "assistant", content: bubble._raw });
  state.streaming = false;
  $("send").disabled = false;
}

function handleEvent(evt, bubble) {
  switch (evt.type) {
    case "sources":
      if (state.config.rag_on) renderSources(evt.sources, true);
      break;
    case "delta":
      bubble._raw = (bubble._raw || "") + evt.text;
      bubble.innerHTML = marked.parse(bubble._raw);
      scrollDown();
      break;
    case "notice":
      console.warn(evt.message);
      break;
    case "error":
      bubble.innerHTML = marked.parse(evt.message);
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

$("menu").addEventListener("click", () => $("sidebar").classList.toggle("open"));

document.querySelectorAll("#suggestions button").forEach((b) =>
  b.addEventListener("click", () => send(b.textContent)));

init();
