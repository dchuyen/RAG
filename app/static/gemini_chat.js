const form = document.querySelector("#chat-form");
      const promptInput = document.querySelector("#prompt");
      const conversation = document.querySelector("#conversation");
      const emptyState = document.querySelector("#empty");
      const sendButton = document.querySelector("#send");
      const conversationNavigation = document.querySelector("#conversation-navigation");
      const scrollToTopButton = document.querySelector("#scroll-to-top");
      const scrollToBottomButton = document.querySelector("#scroll-to-bottom");
      const themeToggle = document.querySelector("#theme-toggle");
      const savedConversationsList = document.querySelector("#saved-conversations");
      const deleteConversationButton = document.querySelector("#delete-conversation");
      const storageStatus = document.querySelector("#storage-status");
      const sidebarToggle = document.querySelector("#sidebar-toggle");
      const sidebarBackdrop = document.querySelector("#sidebar-backdrop");
      const shell = document.querySelector(".shell");
      const history = [];
      const conversationStorageKey = "gemini-chat-conversations";
      let savedConversations = [];
      let currentConversationId = null;

      function setStorageStatus(message, isError = false) {
        storageStatus.textContent = message;
        storageStatus.classList.toggle("error", isError);
      }

      function loadSavedConversations() {
        try {
          const stored = localStorage.getItem(conversationStorageKey);
          if (!stored) {
            refreshSavedConversations();
            return;
          }

          const parsed = JSON.parse(stored);
          if (!Array.isArray(parsed)) {
            throw new Error("Dữ liệu cuộc trò chuyện không đúng định dạng.");
          }
          savedConversations = parsed.filter((item) => (
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
            ))
          ));
          if (savedConversations.length !== parsed.length) {
            setStorageStatus("Một số hội thoại lưu trên trình duyệt không hợp lệ.", true);
          }
          refreshSavedConversations();
        } catch (error) {
          setStorageStatus(`Không thể đọc hội thoại đã lưu: ${error.message}`, true);
        }
      }

      function refreshSavedConversations() {
        savedConversationsList.replaceChildren();
        if (!savedConversations.length) {
          const emptyItem = document.createElement("p");
          emptyItem.className = "history-empty";
          emptyItem.textContent = "Các cuộc trò chuyện của bạn sẽ xuất hiện ở đây.";
          savedConversationsList.append(emptyItem);
        }

        [...savedConversations]
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
            if (item.id === currentConversationId) button.setAttribute("aria-current", "true");

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
        deleteConversationButton.disabled = !currentConversationId || sendButton.disabled;
      }

      function persistCurrentConversation() {
        if (!history.length || !currentConversationId) return;

        const now = new Date().toISOString();
        const existing = savedConversations.find((item) => item.id === currentConversationId);
        const firstUserMessage = history.find((message) => message.role === "user");
        const title = existing?.title
          || firstUserMessage?.content?.replace(/\s+/g, " ").slice(0, 60)
          || "Cuộc trò chuyện mới";
        const conversationData = {
          id: currentConversationId,
          title,
          createdAt: existing?.createdAt || now,
          updatedAt: now,
          messages: history.map(({ role, content, systemData, searchQuery, searchAction }) => ({
            role,
            content,
            ...(typeof systemData === "string" ? { systemData } : {}),
            ...(typeof searchQuery === "string" ? { searchQuery } : {}),
            ...(typeof searchAction === "string" ? { searchAction } : {}),
          })),
        };
        const index = savedConversations.findIndex((item) => item.id === currentConversationId);
        if (index === -1) savedConversations.push(conversationData);
        else savedConversations[index] = conversationData;

        try {
          localStorage.setItem(conversationStorageKey, JSON.stringify(savedConversations));
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

      loadSavedConversations();

      function applyTheme(theme) {
        const isDark = theme === "dark";
        document.body.classList.toggle("theme-dark", isDark);
        document.documentElement.style.colorScheme = isDark ? "dark" : "light";
        if (themeToggle) {
          themeToggle.textContent = isDark ? "☀" : "☾";
          themeToggle.setAttribute("aria-label", isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối");
          themeToggle.setAttribute("aria-pressed", String(isDark));
        }
        try {
          localStorage.setItem("gemini-chat-theme", theme);
        } catch {
          // Ignore storage errors in restricted/private browsing contexts.
        }
      }

      const initializeTheme = () => {
        try {
          const savedTheme = localStorage.getItem("gemini-chat-theme");
          applyTheme(savedTheme === "dark" ? "dark" : "light");
        } catch {
          applyTheme("light");
        }
      };

      initializeTheme();

      function appendInlineMarkdown(parent, text) {
        const pattern = /(`[^`\n]+`|\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)|\*\*([^*\n]+)\*\*|__([^_\n]+)__|~~([^~\n]+)~~|\*([^*\n]+)\*|_([^_\n]+)_)/g;
        let lastIndex = 0;

        for (const match of text.matchAll(pattern)) {
          parent.append(document.createTextNode(text.slice(lastIndex, match.index)));
          const token = match[0];
          let element;

          if (token.startsWith("`")) {
            element = document.createElement("code");
            element.textContent = token.slice(1, -1);
          } else if (token.startsWith("[")) {
            let url;
            try {
              url = new URL(match[3], window.location.href);
            } catch {
              parent.append(document.createTextNode(token));
              lastIndex = match.index + token.length;
              continue;
            }
            if (!["http:", "https:", "mailto:"].includes(url.protocol)) {
              parent.append(document.createTextNode(token));
              lastIndex = match.index + token.length;
              continue;
            }
            element = document.createElement("a");
            element.href = url.href;
            element.rel = "noopener noreferrer";
            if (url.protocol !== "mailto:") element.target = "_blank";
            if (match[4]) element.title = match[4];
            element.textContent = match[2];
          } else {
            const formatting = [
              ["**", "strong", match[5]],
              ["__", "strong", match[6]],
              ["~~", "del", match[7]],
              ["*", "em", match[8]],
              ["_", "em", match[9]],
            ].find(([delimiter]) => token.startsWith(delimiter));
            element = document.createElement(formatting[1]);
            appendInlineMarkdown(element, formatting[2]);
          }

          if (element) {
            parent.append(element);
          }
          lastIndex = match.index + token.length;
        }

        parent.append(document.createTextNode(text.slice(lastIndex)));
      }

      function splitMarkdownTableRow(line) {
        let row = line.trim();
        if (row.startsWith("|")) row = row.slice(1);
        if (row.endsWith("|") && !row.endsWith("\\|")) row = row.slice(0, -1);

        const cells = [];
        let cell = "";
        let codeTicks = 0;
        for (let index = 0; index < row.length; index += 1) {
          const character = row[index];
          if (character === "`") {
            let end = index + 1;
            while (row[end] === "`") end += 1;
            const ticks = end - index;
            if (codeTicks === 0) codeTicks = ticks;
            else if (ticks === codeTicks) codeTicks = 0;
            cell += row.slice(index, end);
            index = end - 1;
          } else if (character === "|" && codeTicks === 0) {
            if (cell.endsWith("\\")) {
              cell = `${cell.slice(0, -1)}|`;
            } else {
              cells.push(cell.trim());
              cell = "";
            }
          } else {
            cell += character;
          }
        }
        cells.push(cell.trim());
        return cells;
      }

      function getMarkdownTable(lines, index) {
        if (index + 1 >= lines.length || !lines[index].includes("|")) return null;

        const headers = splitMarkdownTableRow(lines[index]);
        const separators = splitMarkdownTableRow(lines[index + 1]);
        if (
          headers.length === 0
          || headers.some((cell) => !cell)
          || separators.length !== headers.length
          || separators.some((cell) => !/^:?-{3,}:?$/.test(cell))
        ) {
          return null;
        }

        return {
          headers,
          alignments: separators.map((cell) => (
            cell.startsWith(":") && cell.endsWith(":")
              ? "center"
              : cell.endsWith(":")
                ? "right"
                : cell.startsWith(":")
                  ? "left"
                  : null
          )),
        };
      }

      function appendTableCell(row, tagName, text, alignment) {
        const cell = document.createElement(tagName);
        if (tagName === "th") cell.scope = "col";
        if (alignment) cell.style.textAlign = alignment;
        appendInlineMarkdown(cell, text);
        row.append(cell);
      }

      function isMarkdownBlockStart(lines, index) {
        const line = lines[index];
        return getMarkdownTable(lines, index) !== null
          || /^ {0,3}#{1,6}\s/.test(line)
          || /^ {0,3}```/.test(line)
          || /^ {0,3}>\s?/.test(line)
          || /^\s*(?:[-+*]\s+|\d+[.)]\s+)/.test(line)
          || /^\s*(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/.test(line);
      }

      function renderMarkdown(container, markdown) {
        const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
        let index = 0;

        while (index < lines.length) {
          const line = lines[index];
          if (!line.trim()) {
            index += 1;
            continue;
          }

          const fence = line.match(/^ {0,3}```([^\s`]*)?.*$/);
          if (fence) {
            const codeLines = [];
            index += 1;
            while (index < lines.length && !/^ {0,3}```\s*$/.test(lines[index])) {
              codeLines.push(lines[index]);
              index += 1;
            }
            if (index < lines.length) index += 1;

            const pre = document.createElement("pre");
            const code = document.createElement("code");
            if (fence[1]) code.className = `language-${fence[1].replace(/[^a-zA-Z0-9_-]/g, "")}`;
            code.textContent = codeLines.join("\n");
            pre.append(code);
            container.append(pre);
            continue;
          }

          const tableDefinition = getMarkdownTable(lines, index);
          if (tableDefinition) {
            const wrapper = document.createElement("div");
            wrapper.className = "table-scroll";
            const table = document.createElement("table");
            const thead = document.createElement("thead");
            const headerRow = document.createElement("tr");
            tableDefinition.headers.forEach((header, cellIndex) => {
              appendTableCell(headerRow, "th", header, tableDefinition.alignments[cellIndex]);
            });
            thead.append(headerRow);
            table.append(thead);

            const tbody = document.createElement("tbody");
            index += 2;
            while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
              const cells = splitMarkdownTableRow(lines[index]);
              const row = document.createElement("tr");
              tableDefinition.headers.forEach((_, cellIndex) => {
                appendTableCell(row, "td", cells[cellIndex] ?? "", tableDefinition.alignments[cellIndex]);
              });
              tbody.append(row);
              index += 1;
            }
            table.append(tbody);
            wrapper.append(table);
            container.append(wrapper);
            continue;
          }

          const heading = line.match(/^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
          if (heading) {
            const element = document.createElement(`h${heading[1].length}`);
            appendInlineMarkdown(element, heading[2]);
            container.append(element);
            index += 1;
            continue;
          }

          if (/^\s*(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/.test(line)) {
            container.append(document.createElement("hr"));
            index += 1;
            continue;
          }

          if (/^ {0,3}>\s?/.test(line)) {
            const quoteLines = [];
            while (index < lines.length && /^ {0,3}>\s?/.test(lines[index])) {
              quoteLines.push(lines[index].replace(/^ {0,3}>\s?/, ""));
              index += 1;
            }
            const quote = document.createElement("blockquote");
            renderMarkdown(quote, quoteLines.join("\n"));
            container.append(quote);
            continue;
          }

          const listMatch = line.match(/^\s*(?:[-+*]\s+|\d+[.)]\s+)/);
          if (listMatch) {
            const ordered = /^\s*\d/.test(line);
            const list = document.createElement(ordered ? "ol" : "ul");
            while (index < lines.length) {
              const item = lines[index].match(/^\s*(?:[-+*]\s+|\d+[.)]\s+)(.*)$/);
              if (!item || /^\s*\d/.test(lines[index]) !== ordered) break;
              const listItem = document.createElement("li");
              appendInlineMarkdown(listItem, item[1]);
              list.append(listItem);
              index += 1;
            }
            container.append(list);
            continue;
          }

          const paragraph = [line.trim()];
          index += 1;
          while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines, index)) {
            paragraph.push(lines[index].trim());
            index += 1;
          }
          const element = document.createElement("p");
          appendInlineMarkdown(element, paragraph.join(" "));
          container.append(element);
        }
      }

      function addSystemData(bubble, systemData, searchQuery, searchAction) {
        const hasSearchQuery = typeof searchQuery === "string" && searchQuery.trim();
        const hasSearchAction = typeof searchAction === "string" && searchAction.trim();
        const hasSystemData = typeof systemData === "string" && systemData.trim();
        if (!hasSearchQuery && !hasSearchAction && !hasSystemData) return;

        const details = document.createElement("details");
        details.className = "system-data";
        const summary = document.createElement("summary");
        summary.textContent = "Truy vấn và dữ liệu tìm kiếm";
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
      ) {
        emptyState.hidden = true;
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
            addSystemData(bubble, systemData, searchQuery, searchAction);
          }
        }
        row.append(label, bubble);
        conversation.append(row);
        updateConversationNavigation();
        scrollConversationToBottom();
        return row;
      }

      function renderConversation(messages) {
        history.splice(0, history.length, ...messages);
        conversation.querySelectorAll(".message").forEach((message) => message.remove());
        emptyState.hidden = messages.length > 0;
        messages.forEach(({ role, content, systemData, searchQuery, searchAction }) => (
          addMessage(role, content, false, systemData, searchQuery, searchAction)
        ));
        conversation.scrollTo({ top: conversation.scrollHeight, behavior: "auto" });
        updateConversationNavigation();
      }

      function startNewConversation() {
        if (sendButton.disabled) return;
        currentConversationId = null;
        renderConversation([]);
        refreshSavedConversations();
        setStorageStatus("");
        promptInput.focus();
        closeSidebar();
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
        conversationNavigation.hidden = !hasOverflow;
        scrollToTopButton.disabled = conversation.scrollTop <= 1;
        scrollToBottomButton.disabled = conversation.scrollTop + conversation.clientHeight >= conversation.scrollHeight - 1;
      }

      function scrollConversationToBottom(behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth") {
        conversation.scrollTo({
          top: conversation.scrollHeight,
          behavior,
        });
      }

      conversation.addEventListener("scroll", updateConversationNavigation, { passive: true });
      scrollToTopButton.addEventListener("click", () => {
        conversation.scrollTo({
          top: 0,
          behavior: "auto",
        });
        updateConversationNavigation();
      });
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

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const content = promptInput.value.trim();
        if (!content || sendButton.disabled) return;

        if (!currentConversationId) currentConversationId = createConversationId();
        history.push({ role: "user", content });
        addMessage("user", content);
        promptInput.value = "";
        sendButton.disabled = true;
        sendButton.textContent = "...";
        refreshSavedConversations();
        document.querySelector("#clear").disabled = true;
        const pending = addMessage("assistant", "Đang chờ Gemini trả lời...");
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

        try {
          const response = await fetch("/chat/gemini", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              messages: history.map(({ role, content }) => ({ role, content })),
              temperature: 0.7,
            }),
          });
          const result = await response.json();
          if (!response.ok) {
            const detail = typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail);
            throw new Error(detail || `HTTP ${response.status}`);
          }
          if (typeof result.message !== "string") {
            throw new Error("Phản hồi API không đúng định dạng chat.");
          }
          const systemData = typeof result.system_data === "string" ? result.system_data : null;
          const searchQuery = typeof result.search_query === "string" ? result.search_query : null;
          const searchAction = typeof result.search_action === "string" ? result.search_action : null;
          history.push({
            role: "assistant",
            content: result.message,
            systemData,
            searchQuery,
            searchAction,
          });
          persistCurrentConversation();
          const bubble = pending.querySelector(".bubble");
          bubble.replaceChildren();
          renderMarkdown(bubble, result.message);
          addSystemData(bubble, systemData, searchQuery, searchAction);
          updateConversationNavigation();
          scrollConversationToBottom();
        } catch (error) {
          history.pop();
          pending.remove();
          const errorMessage = addMessage("assistant", `Không gửi được tin nhắn: ${error.message}`, true);
          errorMessage.querySelector(".message-label").append(timer);
        } finally {
          window.clearInterval(timerInterval);
          updateTimer();
          sendButton.disabled = false;
          sendButton.textContent = "Gửi";
          document.querySelector("#clear").disabled = false;
          refreshSavedConversations();
          promptInput.focus();
        }
      });

      promptInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          form.requestSubmit();
        }
      });

      const toggleTheme = () => {
        const nextTheme = document.body.classList.contains("theme-dark") ? "light" : "dark";
        applyTheme(nextTheme);
      };

      if (themeToggle) {
        themeToggle.addEventListener("click", toggleTheme);
      }

      document.querySelector("#clear").addEventListener("click", startNewConversation);

      function deleteSavedConversation(conversationId) {
        const selected = savedConversations.find((item) => item.id === conversationId);
        if (!selected || sendButton.disabled) return;
        if (!window.confirm(`Xóa cuộc trò chuyện "${selected.title}"?`)) return;

        const remaining = savedConversations.filter((item) => item.id !== conversationId);
        try {
          localStorage.setItem(conversationStorageKey, JSON.stringify(remaining));
          savedConversations = remaining;
          if (conversationId === currentConversationId) {
            currentConversationId = null;
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

      savedConversationsList.addEventListener("click", (event) => {
        const deleteButton = event.target.closest("[data-delete-conversation-id]");
        if (deleteButton) {
          deleteSavedConversation(deleteButton.dataset.deleteConversationId);
          return;
        }

        const button = event.target.closest("[data-conversation-id]");
        if (!button || sendButton.disabled) return;
        const selected = savedConversations.find((item) => item.id === button.dataset.conversationId);
        if (!selected) {
          return;
        }
        currentConversationId = selected.id;
        renderConversation(selected.messages);
        refreshSavedConversations();
        setStorageStatus("");
        closeSidebar();
      });

      deleteConversationButton.addEventListener("click", () => {
        if (!currentConversationId) return;
        deleteSavedConversation(currentConversationId);
      });

      sidebarToggle.addEventListener("click", toggleSidebar);
      sidebarBackdrop.addEventListener("click", closeSidebar);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeSidebar();
      });
