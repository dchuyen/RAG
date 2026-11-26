import { renderMarkdown } from "./gemini_chat_markdown.js";

export function createMessageView({
  conversation,
  emptyState,
  history,
  updateConversationNavigation,
  scrollConversationToBottom,
}) {
  function normalizeAssistantMessage(content) {
    try {
      const payload = JSON.parse(content);
      if (
        payload
        && typeof payload === "object"
        && !Array.isArray(payload)
        && payload.action === "answer"
        && typeof payload.answer === "string"
        && payload.answer.trim()
      ) {
        return payload.answer;
      }
    } catch {
      // Regular assistant messages are not JSON.
    }
    return content;
  }

  function addSystemData(
    bubble,
    systemData,
    searchQuery,
    searchAction,
    searchResults,
    searchTimings,
    searchCacheHit,
    searchCacheCosineScore,
    searchCachedQuery,
    chatTimings,
  ) {
    const hasSearchQuery = typeof searchQuery === "string" && searchQuery.trim();
    const hasSearchAction = typeof searchAction === "string" && searchAction.trim();
    const hasSystemData = typeof systemData === "string" && systemData.trim();
    const validSearchTimings = searchTimings && typeof searchTimings === "object" && !Array.isArray(searchTimings)
      ? searchTimings
      : null;
    const validSearchResults = Array.isArray(searchResults)
      ? searchResults.filter((result) => (
        result
        && typeof result.text === "string"
        && result.metadata
        && typeof result.metadata === "object"
        && !Array.isArray(result.metadata)
        && typeof result.relevance_score === "number"
        && Number.isFinite(result.relevance_score)
      ))
      : [];
    if (
      !hasSearchQuery
      && !hasSearchAction
      && !hasSystemData
      && !validSearchResults.length
      && !validSearchTimings
      && !chatTimings
    ) return;

    const details = document.createElement("details");
    details.className = "system-data";
    const summary = document.createElement("summary");
    summary.textContent = hasSearchQuery || hasSystemData || validSearchResults.length
      ? "Truy vấn và dữ liệu tìm kiếm"
      : "Thời gian xử lý";
    details.append(summary);
    if (hasSearchAction) {
      const actionLabel = document.createElement("p");
      actionLabel.className = "system-search-query-label";
      actionLabel.textContent = "JSON do AI tạo";
      const actionCode = document.createElement("pre");
      actionCode.className = "system-search-action";
      const actionContent = document.createElement("code");
      actionContent.textContent = searchAction;
      actionCode.append(actionContent);
      details.append(actionLabel, actionCode);
    }
    if (hasSearchQuery) {
      const queryLabel = document.createElement("p");
      queryLabel.className = "system-search-query-label";
      queryLabel.textContent = "Truy vấn AI gửi đi";
      const query = document.createElement("p");
      query.className = "system-search-query";
      query.textContent = searchQuery;
      details.append(queryLabel, query);
    }
    if (chatTimings && typeof chatTimings === "object" && !Array.isArray(chatTimings)) {
      const chatTimingLabels = [
        ["action_generation_seconds", "Groq: phân tích yêu cầu"],
        ["rag_total_seconds", "Toàn bộ bước RAG"],
        ["answer_generation_seconds", "Groq: tạo câu trả lời"],
        ["server_total_seconds", "Tổng thời gian backend"],
      ];
      const rows = chatTimingLabels.filter(([key]) => (
        typeof chatTimings[key] === "number"
        && Number.isFinite(chatTimings[key])
        && chatTimings[key] >= 0
      ));
      if (rows.length) {
        const timingPanel = document.createElement("section");
        timingPanel.className = "chat-timings";
        timingPanel.setAttribute("aria-label", "Thời gian các bước phản hồi AI");
        const timingHeading = document.createElement("p");
        timingHeading.className = "system-data-label";
        timingHeading.textContent = "Thời gian phản hồi trên máy chủ";
        const timingList = document.createElement("ul");
        timingList.className = "search-timings-list";
        rows.forEach(([key, label]) => {
          const item = document.createElement("li");
          const step = document.createElement("span");
          step.textContent = label;
          const duration = document.createElement("span");
          const seconds = chatTimings[key];
          duration.textContent = seconds < 1
            ? `${(seconds * 1000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} ms`
            : `${seconds.toLocaleString("vi-VN", { minimumFractionDigits: 3, maximumFractionDigits: 3 })} giây`;
          item.append(step, duration);
          timingList.append(item);
        });
        timingPanel.append(timingHeading, timingList);
        details.append(timingPanel);
      }
    }
    if (validSearchTimings) {
      const timingLabels = [
        ["cache_lookup_seconds", "Kiểm tra bộ nhớ đệm"],
        ["search_seconds", "Tìm kiếm web"],
        ["scrape_seconds", "Thu thập nội dung trang"],
        ["chunk_seconds", "Chia văn bản thành đoạn"],
        ["embedding_seconds", "Tạo embedding"],
        ["ranking_seconds", "Xếp hạng kết quả"],
        ["storage_seconds", "Lưu vào vector store"],
      ];
      const rows = timingLabels.filter(([key]) => (
        typeof validSearchTimings[key] === "number"
        && Number.isFinite(validSearchTimings[key])
        && validSearchTimings[key] >= 0
      ));
      if (rows.length) {
        const timingPanel = document.createElement("section");
        timingPanel.className = "search-timings";
        timingPanel.setAttribute("aria-label", "Thời gian từng bước xử lý RAG");
        const timingHeading = document.createElement("p");
        timingHeading.className = "system-data-label";
        timingHeading.textContent = "Thời gian xử lý RAG";
        const timingList = document.createElement("ul");
        timingList.className = "search-timings-list";
        rows.forEach(([key, label]) => {
          const item = document.createElement("li");
          const step = document.createElement("span");
          step.textContent = label;
          const duration = document.createElement("span");
          const seconds = validSearchTimings[key];
          duration.textContent = seconds < 1
            ? `${(seconds * 1000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} ms`
            : `${seconds.toLocaleString("vi-VN", { minimumFractionDigits: 3, maximumFractionDigits: 3 })} giây`;
          item.append(step, duration);
          timingList.append(item);
        });
        timingPanel.append(timingHeading, timingList);
        if (typeof searchCacheHit === "boolean") {
          const cacheStatus = document.createElement("p");
          cacheStatus.className = "search-cache-status";
          cacheStatus.textContent = searchCacheHit
            ? "Kết quả được lấy từ bộ nhớ đệm."
            : "Không dùng kết quả có sẵn trong bộ nhớ đệm.";
          timingPanel.append(cacheStatus);
        }
        if (
          typeof searchCacheCosineScore === "number"
          && Number.isFinite(searchCacheCosineScore)
        ) {
          const cosineStatus = document.createElement("p");
          cosineStatus.className = "search-cache-status";
          cosineStatus.textContent = `Điểm cosine giữa hai truy vấn: ${searchCacheCosineScore.toLocaleString("vi-VN", {
            minimumFractionDigits: 4,
            maximumFractionDigits: 4,
          })}`;
          timingPanel.append(cosineStatus);
          if (typeof searchCachedQuery === "string" && searchCachedQuery.trim()) {
            const cachedQuery = document.createElement("p");
            cachedQuery.className = "search-cache-status";
            cachedQuery.textContent = `Truy vấn cache gần nhất: ${searchCachedQuery}`;
            timingPanel.append(cachedQuery);
          }
        }
        details.append(timingPanel);
      }
    }
    const content = document.createElement("div");
    content.className = "system-data-content";
    if (hasSystemData) {
      const dataLabel = document.createElement("p");
      dataLabel.className = "system-data-label";
      dataLabel.textContent = "Dữ liệu hệ thống cung cấp";
      renderMarkdown(content, systemData);
      details.append(dataLabel, content);
    }
    bubble.append(details);
  }

  function addMessage(
    role,
    content,
    isError = false,
    systemData = null,
    searchQuery = null,
    searchAction = null,
    searchResults = null,
    searchTimings = null,
    searchCacheHit = null,
    searchCacheCosineScore = null,
    searchCachedQuery = null,
    chatTimings = null,
  ) {
    emptyState.hidden = true;
    if (role === "assistant" && !isError) content = normalizeAssistantMessage(content);
    const row = document.createElement("article");
    row.className = `message ${role}${isError ? " error" : ""}`;

    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = role === "user" ? "Bạn" : isError ? "Có lỗi xảy ra" : "Trợ lý";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (isError) bubble.textContent = content;
    else {
      renderMarkdown(bubble, content);
      if (role === "assistant") {
        addSystemData(
          bubble,
          systemData,
          searchQuery,
          searchAction,
          searchResults,
          searchTimings,
          searchCacheHit,
          searchCacheCosineScore,
          searchCachedQuery,
          chatTimings,
        );
      }
    }
    row.append(label, bubble);
    conversation.append(row);
    updateConversationNavigation();
    scrollConversationToBottom();
    return row;
  }

  function renderConversation(messages) {
    const normalizedMessages = messages.map((message) => (
      message.role === "assistant"
        ? { ...message, content: normalizeAssistantMessage(message.content) }
        : message
    ));
    history.splice(0, history.length, ...normalizedMessages);
    conversation.querySelectorAll(".message").forEach((message) => message.remove());
    emptyState.hidden = normalizedMessages.length > 0;
    normalizedMessages.forEach(({
      role,
      content,
      systemData,
      searchQuery,
      searchAction,
      searchResults,
      searchTimings,
      searchCacheHit,
      searchCacheCosineScore,
      searchCachedQuery,
      chatTimings,
    }) => (
      addMessage(
        role,
        content,
        false,
        systemData,
        searchQuery,
        searchAction,
        searchResults,
        searchTimings,
        searchCacheHit,
        searchCacheCosineScore,
        searchCachedQuery,
        chatTimings,
      )
    ));
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: "auto" });
    updateConversationNavigation();
  }

  function renderAssistantResponse(bubble, content, responseDetails) {
    bubble.replaceChildren();
    renderMarkdown(bubble, content);
    addSystemData(
      bubble,
      responseDetails.systemData,
      responseDetails.searchQuery,
      responseDetails.searchAction,
      responseDetails.searchResults,
      responseDetails.searchTimings,
      responseDetails.searchCacheHit,
      responseDetails.searchCacheCosineScore,
      responseDetails.searchCachedQuery,
      responseDetails.chatTimings,
    );
  }

  return {
    addMessage,
    normalizeAssistantMessage,
    renderAssistantResponse,
    renderConversation,
  };
}
