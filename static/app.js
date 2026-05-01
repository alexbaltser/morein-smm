const $ = (q) => document.querySelector(q);
const HISTORY_KEY = "morein_smm_history";

async function loadStyles() {
  const r = await fetch("api/styles");
  const styles = await r.json();
  const sel = $("#style");
  for (const s of styles) {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = `${s.label} — ${s.description}`;
    sel.appendChild(opt);
  }
}

function setupDrop() {
  const drop = $("#drop");
  const file = $("#floorplan");
  const preview = $("#preview");
  const hint = drop.querySelector(".drop-hint");

  const showFile = (f) => {
    if (!f) return;
    const url = URL.createObjectURL(f);
    preview.src = url;
    preview.hidden = false;
    hint.hidden = true;
  };

  drop.addEventListener("click", () => file.click());
  file.addEventListener("change", () => showFile(file.files[0]));

  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("drag");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    const f = e.dataTransfer.files[0];
    if (f) {
      const dt = new DataTransfer();
      dt.items.add(f);
      file.files = dt.files;
      showFile(f);
    }
  });
}

function setStatus(msg, isError = false) {
  const el = $("#status");
  el.hidden = !msg;
  el.innerHTML = "";
  if (!msg) return;
  if (!isError) {
    const sp = document.createElement("div");
    sp.className = "spinner";
    el.appendChild(sp);
  }
  const text = document.createElement("div");
  text.textContent = msg;
  if (isError) text.className = "error";
  el.appendChild(text);
}

function pushHistory(job) {
  const list = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  list.unshift({
    job_id: job.job_id,
    topic: job.topic,
    style: job.style,
    when: new Date().toISOString(),
  });
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 20)));
  renderHistory();
}

function renderHistory() {
  const list = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  const sec = $("#history-section");
  const ul = $("#history");
  if (!list.length) { sec.hidden = true; return; }
  sec.hidden = false;
  ul.innerHTML = "";
  for (const item of list) {
    const li = document.createElement("li");
    const topic = document.createElement("span");
    topic.textContent = item.topic.slice(0, 80) + (item.topic.length > 80 ? "…" : "");
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = new Date(item.when).toLocaleString("ru-RU");
    li.append(topic, when);
    li.addEventListener("click", () => loadJob(item.job_id));
    ul.appendChild(li);
  }
}

async function loadJob(jobId) {
  setStatus("Загружаю джоб…");
  try {
    const r = await fetch(`api/jobs/${jobId}`);
    if (!r.ok) throw new Error("not found");
    const job = await r.json();
    renderResult(job);
    setStatus("");
  } catch (e) {
    setStatus(`Не удалось открыть: ${e.message}`, true);
  }
}

function renderResult(job) {
  $("#result").hidden = false;
  $("#post-text").value = job.post_text;
  $("#post-text").dataset.jobId = job.job_id;

  const grid = $("#images");
  grid.innerHTML = "";
  job.images.forEach((img, idx) => {
    const card = document.createElement("div");
    card.className = "img-card";

    const im = document.createElement("img");
    im.src = img.url;
    im.alt = img.room_ru;
    im.loading = "lazy";

    const meta = document.createElement("div");
    meta.className = "img-meta";
    const label = document.createElement("span");
    label.textContent = img.room_ru;

    const actions = document.createElement("span");
    const dl = document.createElement("button");
    dl.className = "secondary";
    dl.textContent = "Скачать";
    dl.onclick = () => {
      const a = document.createElement("a");
      a.href = img.url;
      a.download = `${job.job_id}_${img.room}.png`;
      a.click();
    };
    const re = document.createElement("button");
    re.className = "secondary";
    re.textContent = "Перегенерировать";
    re.onclick = () => regenImage(job.job_id, idx, im);
    actions.append(dl, re);

    meta.append(label, actions);
    card.append(im, meta);
    grid.appendChild(card);
  });
}

async function regenImage(jobId, idx, imgEl) {
  const extra = prompt("Доп. промпт (опционально, по-английски):", "") || "";
  setStatus("Перегенерирую картинку…");
  try {
    const fd = new FormData();
    fd.append("extra_prompt", extra);
    const r = await fetch(`api/regenerate-image/${jobId}/${idx}`, { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "ошибка");
    imgEl.src = data.image.url;
    setStatus("");
  } catch (e) {
    setStatus(`Ошибка: ${e.message}`, true);
  }
}

async function submitForm(ev) {
  ev.preventDefault();
  const topic = $("#topic").value.trim();
  const style = $("#style").value;
  const n = $("#n_images").value;
  const file = $("#floorplan").files[0];
  if (!topic || !file) return;

  $("#submit").disabled = true;
  setStatus("Анализирую планировку и пишу пост (~10–15 сек)… Затем рендерю комнаты (~30–60 сек).");

  const fd = new FormData();
  fd.append("topic", topic);
  fd.append("style", style);
  fd.append("n_images", n);
  fd.append("floorplan", file);

  try {
    const r = await fetch("api/generate", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "ошибка");
    renderResult(data);
    pushHistory(data);
    setStatus("");
    $("#result").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    setStatus(`Ошибка: ${e.message}`, true);
  } finally {
    $("#submit").disabled = false;
  }
}

$("#gen-form").addEventListener("submit", submitForm);
$("#copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText($("#post-text").value);
  $("#copy").textContent = "Скопировано ✓";
  setTimeout(() => $("#copy").textContent = "Скопировать текст", 1500);
});
$("#regen-text").addEventListener("click", async () => {
  const jobId = $("#post-text").dataset.jobId;
  if (!jobId) return;
  setStatus("Перегенерирую текст…");
  try {
    const r = await fetch(`api/regenerate-text/${jobId}`, { method: "POST" });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "ошибка");
    $("#post-text").value = data.post_text;
    setStatus("");
  } catch (e) {
    setStatus(`Ошибка: ${e.message}`, true);
  }
});

loadStyles();
setupDrop();
renderHistory();
