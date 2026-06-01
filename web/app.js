const state = {
  token: localStorage.getItem("token") || "",
  idToken: localStorage.getItem("idToken") || "",
  user: JSON.parse(localStorage.getItem("user") || "null"),
};

const $ = (id) => document.getElementById(id);
const config = window.AUSSIE_CONFIG || { mode: "local", apiBaseUrl: "" };
const isCloud = config.mode === "cloud";

function setStatus(message) {
  $("status").textContent = message;
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
  const response = await fetch(`${config.apiBaseUrl || ""}${path}`, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
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
    title.textContent = item.filename || "Result";
    card.appendChild(title);
    const tags = document.createElement("code");
    tags.textContent = JSON.stringify(item.tags || item, null, 2);
    card.appendChild(tags);
    if (item.full_url) {
      const url = document.createElement("code");
      url.textContent = item.full_url;
      card.appendChild(url);
    }
    $("results").appendChild(card);
  }
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
      localStorage.clear();
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

  $("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = new FormData(event.target);
    try {
      const data = await api("/api/upload", { method: "POST", body });
      setStatus(data.duplicate ? "Duplicate file, existing record returned" : "Uploaded");
      renderResults(data.media);
    } catch (error) {
      setStatus(error.message);
    }
  });

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
