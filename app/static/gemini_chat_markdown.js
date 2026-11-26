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

export function renderMarkdown(container, markdown) {
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
