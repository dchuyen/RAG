import { initializeConversationLibrary } from "./gemini_chat_conversations.js";
import { createMessageView } from "./gemini_chat_messages.js";
import { initializeSettings, initializeTheme } from "./gemini_chat_settings.js";

const form = document.querySelector("#chat-form");
const promptInput = document.querySelector("#prompt");
const conversation = document.querySelector("#conversation");
const emptyState = document.querySelector("#empty");
const sendButton = document.querySelector("#send");
const conversationNavigation = document.querySelector("#conversation-navigation");
const scrollToBottomButton = document.querySelector("#scroll-to-bottom");
const themeToggle = document.querySelector("#theme-toggle");
const sidebarToggle = document.querySelector("#sidebar-toggle");
const sidebarBackdrop = document.querySelector("#sidebar-backdrop");
const shell = document.querySelector(".shell");
const history = [];
const conversationState = {
  history,
  savedConversations: [],
  currentConversationId: null,
};

async function readChatStream(response, onChunk) {
  if (!response.body) throw new Error("Trình duyệt không hỗ trợ đọc phản hồi streaming.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metadata = null;
  let chatTimings = null;
  let completed = false;

  function processLine(line) {
    if (!line.trim()) return;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      throw new Error("Dữ liệu streaming từ máy chủ không hợp lệ.");
    }

    if (event.type === "metadata") {
      metadata = event;
    } else if (event.type === "chunk" && typeof event.content === "string") {
      onChunk(event.content);
    } else if (event.type === "done") {
      completed = true;
      chatTimings = event.chat_timings;
    } else if (event.type === "error") {
      throw new Error(typeof event.detail === "string" ? event.detail : "Không thể tạo phản hồi.");
    } else {
      throw new Error("Máy chủ gửi sự kiện streaming không hợp lệ.");
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline !== -1) {
        processLine(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
        newline = buffer.indexOf("\n");
      }
    }
    if (buffer.trim()) processLine(buffer);
  } finally {
    reader.releaseLock();
  }

  if (!metadata || !completed) {
    throw new Error("Phản hồi streaming bị kết thúc trước khi hoàn tất.");
  }
  return { metadata, chatTimings };
}

function closeSidebar() {
  shell.classList.remove("sidebar-open");
  sidebarToggle.setAttribute("aria-expanded", "false");
  sidebarToggle.setAttribute("aria-label", "Mở lịch sử chat");
  sidebarBackdrop.hidden = true;
}

function toggleSidebar() {
  const isOpen = shell.classList.toggle("sidebar-open");
  sidebarToggle.setAttribute("aria-expanded", String(isOpen));
  sidebarToggle.setAttribute("aria-label", isOpen ? "Đóng lịch sử chat" : "Mở lịch sử chat");
  sidebarBackdrop.hidden = !isOpen;
}

function updateConversationNavigation() {
  const hasOverflow = conversation.scrollHeight > conversation.clientHeight + 1;
  const isAtBottom = conversation.scrollTop + conversation.clientHeight >= conversation.scrollHeight - 1;
  conversationNavigation.hidden = !hasOverflow || isAtBottom;
}

function scrollConversationToBottom(
  behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
) {
  conversation.scrollTo({
    top: conversation.scrollHeight,
    behavior,
  });
}

const messageView = createMessageView({
  conversation,
  emptyState,
  history,
  updateConversationNavigation,
  scrollConversationToBottom,
});
const conversationLibrary = initializeConversationLibrary({
  state: conversationState,
  sendButton,
  promptInput,
  renderConversation: messageView.renderConversation,
  closeSidebar,
});
const settings = initializeSettings();
initializeTheme(themeToggle);

conversation.addEventListener("scroll", updateConversationNavigation, { passive: true });
scrollToBottomButton.addEventListener("click", () => {
  scrollConversationToBottom("auto");
  updateConversationNavigation();
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.textContent;
    promptInput.focus();
  });
});

async function sendMessage(content, isRetry = false) {
  if (!content || sendButton.disabled) return;

  if (!conversationState.currentConversationId) {
    conversationState.currentConversationId = conversationLibrary.createConversationId();
  }
  history.push({ role: "user", content });
  if (!isRetry) {
    messageView.addMessage("user", content);
    promptInput.value = "";
  }
  sendButton.disabled = true;
  sendButton.textContent = "...";
  conversationLibrary.refreshSavedConversations();
  document.querySelector("#clear").disabled = true;
  const provider = "groq";
  const pending = messageView.addMessage("assistant", "Đang chờ Groq trả lời...");
  const timer = document.createElement("span");
  timer.className = "response-timer";
  timer.setAttribute("role", "timer");
  timer.setAttribute("aria-label", "Thời gian phản hồi");
  const startedAt = performance.now();
  const updateTimer = () => {
    timer.textContent = `· ${((performance.now() - startedAt) / 1000).toLocaleString("vi-VN", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })} giây`;
  };
  pending.querySelector(".message-label").append(timer);
  updateTimer();
  const timerInterval = window.setInterval(updateTimer, 100);
  let streamedMessage = "";

  try {
    const response = await fetch(`/chat/${provider}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: history.map(({ role, content: messageContent }) => ({
          role,
          content: messageContent,
        })),
        temperature: 0.7,
        ...settings.getRequestSettings(),
      }),
    });
    if (!response.ok) {
      let errorPayload = {};
      try {
        errorPayload = await response.json();
      } catch {
        errorPayload = {};
      }
      const detail = typeof errorPayload.detail === "string"
        ? errorPayload.detail
        : JSON.stringify(errorPayload.detail);
      throw new Error(detail || `HTTP ${response.status}`);
    }
    const bubble = pending.querySelector(".bubble");
    const { metadata, chatTimings: streamedChatTimings } = await readChatStream(
      response,
      (chunk) => {
        streamedMessage += chunk;
        bubble.textContent = streamedMessage;
        updateConversationNavigation();
        scrollConversationToBottom("auto");
      },
    );
    const result = {
      ...metadata,
      chat_timings: streamedChatTimings,
      message: streamedMessage,
    };
    if (typeof result.message !== "string") {
      throw new Error("Phản hồi API không đúng định dạng chat.");
    }
    const assistantMessage = messageView.normalizeAssistantMessage(result.message);
    const systemData = typeof result.system_data === "string" ? result.system_data : null;
    const searchQuery = typeof result.search_query === "string" ? result.search_query : null;
    const searchAction = typeof result.search_action === "string" ? result.search_action : null;
    const searchResults = Array.isArray(result.search_results) ? result.search_results : null;
    const searchTimings = result.search_timings && typeof result.search_timings === "object"
      && !Array.isArray(result.search_timings)
      ? result.search_timings
      : null;
    const chatTimings = result.chat_timings && typeof result.chat_timings === "object"
      && !Array.isArray(result.chat_timings)
      ? result.chat_timings
      : null;
    const searchCacheHit = typeof result.search_cache_hit === "boolean" ? result.search_cache_hit : null;
    const searchCacheCosineScore = typeof result.search_cache_cosine_score === "number"
      && Number.isFinite(result.search_cache_cosine_score)
      ? result.search_cache_cosine_score
      : null;
    const searchCachedQuery = typeof result.search_cached_query === "string"
      ? result.search_cached_query
      : null;
    history.push({
      role: "assistant",
      content: assistantMessage,
      systemData,
      searchQuery,
      searchAction,
      searchResults,
      searchTimings,
      chatTimings,
      searchCacheHit,
      searchCacheCosineScore,
      searchCachedQuery,
    });
    conversationLibrary.persistCurrentConversation();
    messageView.renderAssistantResponse(bubble, assistantMessage, {
      systemData,
      searchQuery,
      searchAction,
      searchResults,
      searchTimings,
      searchCacheHit,
      searchCacheCosineScore,
      searchCachedQuery,
      chatTimings,
    });
    updateConversationNavigation();
    scrollConversationToBottom();
  } catch (error) {
    if (history.at(-1)?.role === "assistant") history.pop();
    if (history.at(-1)?.role === "user") history.pop();
    if (streamedMessage) {
      pending.querySelector(".bubble").textContent = streamedMessage;
    } else {
      pending.remove();
    }
    const errorMessage = messageView.addMessage(
      "assistant",
      `Không gửi được tin nhắn: ${error.message}`,
      true,
    );
    errorMessage.querySelector(".message-label").append(timer);
    const retryButton = document.createElement("button");
    retryButton.className = "retry-button";
    retryButton.type = "button";
    retryButton.textContent = "Thử lại";
    retryButton.setAttribute("aria-label", "Thử gửi lại tin nhắn cho Groq");
    retryButton.addEventListener("click", () => {
      if (sendButton.disabled) return;
      errorMessage.remove();
      pending.remove();
      void sendMessage(content, true);
    });
    errorMessage.querySelector(".bubble").append(document.createElement("br"), retryButton);
  } finally {
    window.clearInterval(timerInterval);
    updateTimer();
    sendButton.disabled = false;
    sendButton.textContent = "Gửi";
    document.querySelector("#clear").disabled = false;
    conversationLibrary.refreshSavedConversations();
    promptInput.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void sendMessage(promptInput.value.trim());
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

sidebarToggle.addEventListener("click", toggleSidebar);
sidebarBackdrop.addEventListener("click", closeSidebar);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSidebar();
});
