const state = {
  token: localStorage.getItem("token") || "",
  idToken: localStorage.getItem("idToken") || "",
  user: JSON.parse(localStorage.getItem("user") || "null"),
};

const $ = (id) => document.getElementById(id);
const config = window.AUSSIE_CONFIG || { mode: "local", apiBaseUrl: "" };
const isCloud = config.mode === "cloud";

function clearSession() {
  state.token = "";
  state.idToken = "";
  state.user = null;
  localStorage.removeItem("token");
  localStorage.removeItem("idToken");
  localStorage.removeItem("user");
}

function tokenExpired(token) {
  if (!token) return true;
  try {
    const claims = decodeJwt(token);
    return Number(claims.exp || 0) * 1000 <= Date.now();
  } catch (_error) {
    return true;
  }
}

if (isCloud && tokenExpired(state.idToken)) {
  clearSession();
}

function setStatus(message) {
  $("status").textContent = message;
}

function summarizeFiles(files) {
  if (!files.length) return "Images or videos, multiple files allowed";
  const totalMb = files.reduce((sum, file) => sum + file.size, 0) / (1024 * 1024);
  return `${files.length} file${files.length === 1 ? "" : "s"} selected, ${totalMb.toFixed(1)} MB total`;
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error(`Could not read ${file.name}`));
    };
    image.src = url;
  });
}

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Image compression failed"))), type, quality);
  });
}

async function prepareUploadFile(file) {
  const maxDirectBytes = 4.5 * 1024 * 1024;
  if (!isCloud || !file.type.startsWith("image/") || file.size <= maxDirectBytes) return file;
  const image = await loadImage(file);
  const maxSide = 1600;
  const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  context.drawImage(image, 0, 0, width, height);
  const blob = await canvasBlob(canvas, "image/jpeg", 0.82);
  return new File([blob], file.name, { type: "image/jpeg", lastModified: file.lastModified });
}

function showApp() {
  $("auth-panel").classList.toggle("hidden", !!state.token);
  $("app-panel").classList.toggle("hidden", !state.token);
  $("signout").classList.toggle("hidden", !state.token);
  $("user-label").textContent = state.user ? `${state.user.first_name} ${state.user.last_name}` : "";
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) headers["content-type"] = "application/json";
  const bearer = state.idToken || state.token;
  if (bearer) headers.authorization = `Bearer ${bearer}`;
  let response;
  try {
    response = await fetch(`${config.apiBaseUrl || ""}${path}`, { ...options, headers });
  } catch (error) {
    if (isCloud) throw new Error(`Cloud request failed: ${error.message}`);
    throw error;
  }
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_error) {
    data = { error: text };
  }
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      if (isCloud && tokenExpired(state.idToken)) {
        clearSession();
        showApp();
        throw new Error("Session expired. Please sign in again.");
      }
      throw new Error(data.message || data.error || `Cloud API rejected the request (${response.status}).`);
    }
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function base64UrlEncode(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function sha256(text) {
  return crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
}

function randomString(length = 64) {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

function decodeJwt(token) {
  const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(payload));
}

async function cognitoRedirect(screen) {
  const verifier = randomString();
  const challenge = base64UrlEncode(await sha256(verifier));
  localStorage.setItem("pkceVerifier", verifier);
  const params = new URLSearchParams({
    client_id: config.cognitoClientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: config.redirectUri || window.location.origin + "/",
    code_challenge_method: "S256",
    code_challenge: challenge,
  });
  if (screen === "signup") params.set("screen_hint", "signup");
  window.location.href = `${config.cognitoDomain}/oauth2/authorize?${params}`;
}

async function handleCognitoCallback() {
  if (!isCloud) return;
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  if (!code) return;
  const verifier = localStorage.getItem("pkceVerifier");
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.cognitoClientId,
    code,
    redirect_uri: config.redirectUri || window.location.origin + "/",
    code_verifier: verifier,
  });
  const response = await fetch(`${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });
  const tokens = await response.json();
  if (!response.ok) throw new Error(tokens.error_description || "Cognito token exchange failed");
  const claims = decodeJwt(tokens.id_token);
  state.idToken = tokens.id_token;
  state.token = tokens.access_token;
  state.user = {
    email: claims.email,
    first_name: claims.given_name || claims.email,
    last_name: claims.family_name || "",
  };
  localStorage.setItem("idToken", state.idToken);
  localStorage.setItem("token", state.token);
  localStorage.setItem("user", JSON.stringify(state.user));
  localStorage.removeItem("pkceVerifier");
  window.history.replaceState({}, document.title, window.location.pathname);
}

function formJson(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function urlsFrom(text) {
  return text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
}

function tagsFrom(text) {
  return text.split(",").map((tag) => tag.trim()).filter(Boolean);
}

function renderResults(items) {
  const results = Array.isArray(items) ? items : [items];
  $("results").innerHTML = "";
  for (const item of results) {
    const card = document.createElement("article");
    card.className = "result";
    if (item.error) card.classList.add("error");
    if (item.thumbnail_url) {
      const link = document.createElement("a");
      link.href = item.full_url;
      link.target = "_blank";
      const img = document.createElement("img");
      img.src = item.thumbnail_url;
      img.alt = item.filename || "thumbnail";
      link.appendChild(img);
      card.appendChild(link);
    }
    const title = document.createElement("strong");
    title.textContent = item.filename || item.file || "Result";
    card.appendChild(title);
    if (item.media_type) card.appendChild(mediaBadge(item.media_type));
    if (item.error) {
      card.appendChild(errorBlock(item.error));
    } else if (item.tags) {
      card.appendChild(tagsBlock(item.tags));
    }
    if (item.thumbnail_url) {
      card.appendChild(urlBlock("Thumbnail URL", item.thumbnail_url));
    }
    if (item.full_url && !item.thumbnail_url) {
      card.appendChild(openOriginalBlock(item.full_url, item.media_type));
      card.appendChild(urlBlock("Full image URL", item.full_url));
    }
    if (item.frame_urls && item.frame_urls.length) {
      card.appendChild(framesBlock(item.frame_urls));
    }
    $("results").appendChild(card);
  }
}

function mediaBadge(mediaType) {
  const badge = document.createElement("span");
  badge.className = `media-badge ${mediaType === "video" ? "video" : "image"}`;
  badge.textContent = mediaType === "video" ? "Video" : "Image";
  return badge;
}

function errorBlock(message) {
  const block = document.createElement("div");
  block.className = "error-message";
  block.textContent = message;
  return block;
}

function tagsBlock(tags) {
  const wrapper = document.createElement("div");
  wrapper.className = "tag-list";
  const entries = Object.entries(tags || {}).filter(([, value]) => typeof value === "number" || typeof value === "string");
  if (!entries.length) {
    const empty = document.createElement("span");
    empty.className = "tag-chip muted-chip";
    empty.textContent = "No tags";
    wrapper.appendChild(empty);
    return wrapper;
  }
  for (const [tag, count] of entries) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    const name = document.createElement("span");
    name.textContent = tag;
    chip.appendChild(name);
    if (Number(count) > 1) {
      const badge = document.createElement("strong");
      badge.textContent = `x${count}`;
      chip.appendChild(badge);
    }
    wrapper.appendChild(chip);
  }
  return wrapper;
}

function urlBlock(label, value) {
  const wrapper = document.createElement("div");
  wrapper.className = "url-block";
  const head = document.createElement("div");
  head.className = "url-head";
  const title = document.createElement("span");
  title.textContent = label;
  const actions = document.createElement("div");
  actions.className = "url-actions";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "copy";
  toggle.textContent = "Show";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "copy";
  copy.textContent = "Copy";
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(value);
    copy.textContent = "Copied";
    setStatus(`${label} copied`);
    window.setTimeout(() => {
      copy.textContent = "Copy";
    }, 1600);
  });
  actions.append(toggle, copy);
  head.append(title, actions);
  const code = document.createElement("code");
  code.className = "collapsed";
  code.textContent = value;
  toggle.addEventListener("click", () => {
    const collapsed = code.classList.toggle("collapsed");
    toggle.textContent = collapsed ? "Show" : "Hide";
  });
  wrapper.append(head, code);
  return wrapper;
}

function openOriginalBlock(url, mediaType = "image") {
  const wrapper = document.createElement("div");
  wrapper.className = "open-original";
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = mediaType === "video" ? "Open original video" : "Open original image";
  wrapper.appendChild(link);
  return wrapper;
}

function framesBlock(frameUrls) {
  const wrapper = document.createElement("div");
  wrapper.className = "frames-block";
  const title = document.createElement("div");
  title.className = "frames-title";
  title.textContent = `Extracted frames (${frameUrls.length})`;
  const grid = document.createElement("div");
  grid.className = "frames-grid";
  frameUrls.forEach((url, index) => {
    const item = document.createElement("div");
    item.className = "frame-item";
    const img = document.createElement("img");
    img.src = url;
    img.alt = `Extracted frame ${index + 1}`;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "copy";
    copy.textContent = `Copy frame ${index + 1}`;
    copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(url);
      copy.textContent = "Copied";
      setStatus(`Frame ${index + 1} URL copied`);
      window.setTimeout(() => {
        copy.textContent = `Copy frame ${index + 1}`;
      }, 1600);
    });
    item.append(img, copy);
    grid.appendChild(item);
  });
  wrapper.append(title, grid);
  return wrapper;
}

async function uploadOne(file) {
  const uploadFile = await prepareUploadFile(file);
  const body = new FormData();
  body.append("file", uploadFile, file.name);
  const data = await api("/api/upload", { method: "POST", body });
  return { ...data.media, duplicate: data.duplicate };
}

function wireUploadForm(formId, summaryId, emptyLabel) {
  const form = $(formId);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const files = Array.from(event.target.elements.file.files || []);
    if (!files.length) {
      setStatus("Choose at least one file");
      return;
    }
    try {
      let completed = 0;
      setStatus(`Uploading 0/${files.length}`);
      const uploads = files.map(async (file) => {
        try {
          return await uploadOne(file);
        } catch (error) {
          return { file: file.name, error: error.message };
        } finally {
          completed += 1;
          setStatus(`Uploading ${completed}/${files.length}`);
        }
      });
      const results = await Promise.all(uploads);
      const failed = results.filter((item) => item.error).length;
      const duplicates = results.filter((item) => item.duplicate).length;
      setStatus(
        failed
          ? `Uploaded ${results.length - failed}/${results.length}; ${failed} failed`
          : `Uploaded ${results.length} file${results.length === 1 ? "" : "s"}${duplicates ? `, ${duplicates} duplicate` : ""}`
      );
      renderResults(results);
    } catch (error) {
      setStatus(error.message);
    }
  });

  form.elements.file.addEventListener("change", (event) => {
    const files = Array.from(event.target.files || []);
    $(summaryId).textContent = files.length ? summarizeFiles(files) : emptyLabel;
  });
}

function wireForms() {
  $("signup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isCloud) {
      await cognitoRedirect("signup");
      return;
    }
    try {
      const data = await api("/api/auth/signup", { method: "POST", body: JSON.stringify(formJson(event.target)) });
      setStatus(data.message);
    } catch (error) {
      setStatus(error.message);
    }
  });

  $("signin-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isCloud) {
      await cognitoRedirect("signin");
      return;
    }
    try {
      const data = await api("/api/auth/signin", { method: "POST", body: JSON.stringify(formJson(event.target)) });
      state.token = data.token;
      state.user = data.user;
      localStorage.setItem("token", state.token);
      localStorage.setItem("user", JSON.stringify(state.user));
      showApp();
      setStatus("Signed in");
    } catch (error) {
      setStatus(error.message);
    }
  });

  $("signout").addEventListener("click", async () => {
    try {
      if (!isCloud) await api("/api/auth/signout", { method: "POST", body: "{}" });
    } finally {
      state.token = "";
      state.idToken = "";
      state.user = null;
      clearSession();
      if (isCloud) {
        const params = new URLSearchParams({
          client_id: config.cognitoClientId,
          logout_uri: config.logoutUri || window.location.origin + "/",
        });
        window.location.href = `${config.cognitoDomain}/logout?${params}`;
        return;
      }
      showApp();
    }
  });

  wireUploadForm("image-upload-form", "image-upload-file-summary", "Multiple images allowed");
  wireUploadForm("video-upload-form", "video-upload-file-summary", "Use short demo videos");

  $("tag-query-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const tags = JSON.parse(new FormData(event.target).get("tags"));
      const data = await api("/api/query/tags", { method: "POST", body: JSON.stringify({ tags }) });
      renderResults(data.results);
    } catch (error) {
      setStatus(error.message);
    }
  });

  $("species-query-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = await api("/api/query/species", { method: "POST", body: JSON.stringify(formJson(event.target)) });
    renderResults(data.results);
  });

  $("thumb-query-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = await api("/api/query/thumbnail", { method: "POST", body: JSON.stringify(formJson(event.target)) });
    renderResults(data);
  });

  $("file-query-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = await api("/api/query/file", { method: "POST", body: new FormData(event.target) });
    renderResults(data.results);
  });

  $("edit-tags-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = formJson(event.target);
    const data = await api("/api/tags/edit", {
      method: "POST",
      body: JSON.stringify({ urls: urlsFrom(form.urls), tags: tagsFrom(form.tags), operation: Number(form.operation) }),
    });
    renderResults(data.updated);
  });

  $("delete-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = formJson(event.target);
    const data = await api("/api/delete", { method: "POST", body: JSON.stringify({ urls: urlsFrom(form.urls) }) });
    renderResults(data);
  });

  $("watch-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = formJson(event.target);
    const data = await api("/api/notifications/watch", {
      method: "POST",
      body: JSON.stringify({ email: form.email, tags: tagsFrom(form.tags) }),
    });
    setStatus(data.ok ? "Watch list updated" : "Watch failed");
  });
}

handleCognitoCallback()
  .catch((error) => setStatus(error.message))
  .finally(() => {
    wireForms();
    showApp();
  });
