const API_BASE = window.location.origin;

function getUserName() {
  return localStorage.getItem("sha_user_name") || "";
}

function setUserName(name) {
  localStorage.setItem("sha_user_name", name);
}

function getAuthToken() {
  return localStorage.getItem("sha_auth_token") || "";
}

function setAuthToken(token) {
  localStorage.setItem("sha_auth_token", token);
}

function clearUserName() {
  localStorage.removeItem("sha_user_name");
}

function clearAuthToken() {
  localStorage.removeItem("sha_auth_token");
}

function requireLogin() {
  if (!getUserName() || !getAuthToken()) {
    window.location.href = "/frontend/login.html";
  }
}

function logout() {
  clearUserName();
  clearAuthToken();
  window.location.href = "/frontend/login.html";
}

function formatApiError(payload, fallbackMessage) {
  if (!payload) {
    return fallbackMessage;
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => item.msg || item.message || JSON.stringify(item))
      .join(", ");
  }

  if (typeof payload.message === "string") {
    return payload.message;
  }

  return fallbackMessage;
}

async function authFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    logout();
    throw new Error("Please login again.");
  }

  return response;
}

function pushChatHistory(question, answer) {
  const oldItems = JSON.parse(localStorage.getItem("sha_chat_history") || "[]");
  oldItems.unshift({
    question,
    answer,
    at: new Date().toISOString(),
  });
  localStorage.setItem("sha_chat_history", JSON.stringify(oldItems.slice(0, 50)));
}

function getChatHistory() {
  return JSON.parse(localStorage.getItem("sha_chat_history") || "[]");
}
