const CONVERSATION_STORAGE_KEY = "gemini-chat-conversations";

export function initializeConversationLibrary({
  state,
  sendButton,
  promptInput,
  renderConversation,
  closeSidebar,
}) {
  const savedConversationsList = document.querySelector("#saved-conversations");
  const deleteConversationButton = document.querySelector("#delete-conversation");
  const storageStatus = document.querySelector("#storage-status");

  function setStorageStatus(message, isError = false) {
    storageStatus.textContent = message;
    storageStatus.classList.toggle("error", isError);
  }

  function refreshSavedConversations() {
    savedConversationsList.replaceChildren();
    if (!state.savedConversations.length) {
      const emptyItem = document.createElement("p");
      emptyItem.className = "history-empty";
      emptyItem.textContent = "Các cuộc trò chuyện của bạn sẽ xuất hiện ở đây.";
      savedConversationsList.append(emptyItem);
    }

    [...state.savedConversations]
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
      .forEach((item) => {
        const listItem = document.createElement("div");
        listItem.className = "conversation-row";
        listItem.setAttribute("role", "listitem");
        const button = document.createElement("button");
        button.className = "conversation-item";
        button.type = "button";
        button.dataset.conversationId = item.id;
        button.disabled = sendButton.disabled;
        if (item.id === state.currentConversationId) button.setAttribute("aria-current", "true");

        const title = document.createElement("span");
        title.className = "conversation-title";
        title.textContent = item.title;
        const updatedAt = document.createElement("span");
        updatedAt.className = "conversation-date";
        updatedAt.textContent = new Date(item.updatedAt).toLocaleString("vi-VN", {
          dateStyle: "short",
          timeStyle: "short",
        });
        const deleteButton = document.createElement("button");
        deleteButton.className = "conversation-delete";
        deleteButton.type = "button";
        deleteButton.dataset.deleteConversationId = item.id;
        deleteButton.disabled = sendButton.disabled;
        deleteButton.title = "Xóa cuộc trò chuyện";
        deleteButton.setAttribute("aria-label", `Xóa cuộc trò chuyện “${item.title}”`);
        deleteButton.textContent = "×";
        button.append(title, updatedAt);
        listItem.append(button, deleteButton);
        savedConversationsList.append(listItem);
      });
    deleteConversationButton.disabled = !state.currentConversationId || sendButton.disabled;
  }

  function loadSavedConversations() {
    try {
      const stored = localStorage.getItem(CONVERSATION_STORAGE_KEY);
      if (!stored) {
        refreshSavedConversations();
        return;
      }

      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) {
        throw new Error("Dữ liệu cuộc trò chuyện không đúng định dạng.");
      }
      state.savedConversations = parsed.filter((item) => (
        item
        && typeof item.id === "string"
        && typeof item.title === "string"
        && typeof item.createdAt === "string"
        && typeof item.updatedAt === "string"
        && Array.isArray(item.messages)
        && item.messages.every((message) => (
          message
          && ["user", "assistant"].includes(message.role)
          && typeof message.content === "string"
          && (message.systemData === undefined || typeof message.systemData === "string")
          && (message.searchQuery === undefined || typeof message.searchQuery === "string")
          && (message.searchAction === undefined || typeof message.searchAction === "string")
          && (
            message.searchTimings === undefined
            || (
              message.searchTimings
              && typeof message.searchTimings === "object"
              && !Array.isArray(message.searchTimings)
              && Object.values(message.searchTimings).every((duration) => (
                typeof duration === "number" && Number.isFinite(duration) && duration >= 0
              ))
            )
          )
          && (
            message.chatTimings === undefined
            || (
              message.chatTimings
              && typeof message.chatTimings === "object"
              && !Array.isArray(message.chatTimings)
              && Object.values(message.chatTimings).every((duration) => (
                typeof duration === "number" && Number.isFinite(duration) && duration >= 0
              ))
            )
          )
          && (message.searchCacheHit === undefined || typeof message.searchCacheHit === "boolean")
          && (message.searchCacheCosineScore === undefined || (
            typeof message.searchCacheCosineScore === "number"
            && Number.isFinite(message.searchCacheCosineScore)
          ))
          && (message.searchCachedQuery === undefined || typeof message.searchCachedQuery === "string")
          && (
            message.searchResults === undefined
            || (
              Array.isArray(message.searchResults)
              && message.searchResults.every((result) => (
                result
                && typeof result.text === "string"
                && result.metadata
                && typeof result.metadata === "object"
                && !Array.isArray(result.metadata)
                && typeof result.relevance_score === "number"
                && Number.isFinite(result.relevance_score)
              ))
            )
          )
        ))
      ));
      if (state.savedConversations.length !== parsed.length) {
        setStorageStatus("Một số hội thoại lưu trên trình duyệt không hợp lệ.", true);
      }
      refreshSavedConversations();
    } catch (error) {
      setStorageStatus(`Không thể đọc hội thoại đã lưu: ${error.message}`, true);
    }
  }

  function persistCurrentConversation() {
    if (!state.history.length || !state.currentConversationId) return;

    const now = new Date().toISOString();
    const existing = state.savedConversations.find((item) => item.id === state.currentConversationId);
    const firstUserMessage = state.history.find((message) => message.role === "user");
    const title = existing?.title
      || firstUserMessage?.content?.replace(/\s+/g, " ").slice(0, 60)
      || "Cuộc trò chuyện mới";
    const conversationData = {
      id: state.currentConversationId,
      title,
      createdAt: existing?.createdAt || now,
      updatedAt: now,
      messages: state.history.map(({
        role,
        content,
        systemData,
        searchQuery,
        searchAction,
        searchResults,
        searchTimings,
        chatTimings,
        searchCacheHit,
        searchCacheCosineScore,
        searchCachedQuery,
      }) => ({
        role,
        content,
        ...(typeof systemData === "string" ? { systemData } : {}),
        ...(typeof searchQuery === "string" ? { searchQuery } : {}),
        ...(typeof searchAction === "string" ? { searchAction } : {}),
        ...(Array.isArray(searchResults) ? { searchResults } : {}),
        ...(searchTimings && typeof searchTimings === "object" ? { searchTimings } : {}),
        ...(chatTimings && typeof chatTimings === "object" ? { chatTimings } : {}),
        ...(typeof searchCacheHit === "boolean" ? { searchCacheHit } : {}),
        ...(typeof searchCacheCosineScore === "number" ? { searchCacheCosineScore } : {}),
        ...(typeof searchCachedQuery === "string" ? { searchCachedQuery } : {}),
      })),
    };
    const index = state.savedConversations.findIndex((item) => item.id === state.currentConversationId);
    if (index === -1) state.savedConversations.push(conversationData);
    else state.savedConversations[index] = conversationData;

    try {
      localStorage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(state.savedConversations));
      refreshSavedConversations();
      setStorageStatus("Đã lưu trên trình duyệt này.");
    } catch (error) {
      setStorageStatus(`Không thể lưu hội thoại: ${error.message}`, true);
    }
  }

  function createConversationId() {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  function startNewConversation() {
    if (sendButton.disabled) return;
    state.currentConversationId = null;
    renderConversation([]);
    refreshSavedConversations();
    setStorageStatus("");
    promptInput.focus();
    closeSidebar();
  }

  function deleteSavedConversation(conversationId) {
    const selected = state.savedConversations.find((item) => item.id === conversationId);
    if (!selected || sendButton.disabled) return;
    if (!window.confirm(`Xóa cuộc trò chuyện "${selected.title}"?`)) return;

    const remaining = state.savedConversations.filter((item) => item.id !== conversationId);
    try {
      localStorage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(remaining));
      state.savedConversations = remaining;
      if (conversationId === state.currentConversationId) {
        state.currentConversationId = null;
        renderConversation([]);
        promptInput.focus();
        closeSidebar();
      }
      refreshSavedConversations();
      setStorageStatus("Đã xóa cuộc trò chuyện.");
    } catch (error) {
      setStorageStatus(`Không thể xóa hội thoại: ${error.message}`, true);
    }
  }

  document.querySelector("#clear").addEventListener("click", startNewConversation);
  savedConversationsList.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-conversation-id]");
    if (deleteButton) {
      deleteSavedConversation(deleteButton.dataset.deleteConversationId);
      return;
    }

    const button = event.target.closest("[data-conversation-id]");
    if (!button || sendButton.disabled) return;
    const selected = state.savedConversations.find((item) => item.id === button.dataset.conversationId);
    if (!selected) {
      return;
    }
    state.currentConversationId = selected.id;
    renderConversation(selected.messages);
    refreshSavedConversations();
    setStorageStatus("");
    closeSidebar();
  });

  deleteConversationButton.addEventListener("click", () => {
    if (!state.currentConversationId) return;
    deleteSavedConversation(state.currentConversationId);
  });

  loadSavedConversations();
  return {
    createConversationId,
    persistCurrentConversation,
    refreshSavedConversations,
    setStorageStatus,
    startNewConversation,
  };
}
