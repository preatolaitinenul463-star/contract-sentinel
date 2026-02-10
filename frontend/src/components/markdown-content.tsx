"use client";

/**
 * 轻量 Markdown 渲染组件（无第三方依赖）
 * 支持：标题、加粗、列表、代码块、链接、分割线
 * 安全：链接协议白名单（仅 http/https）、属性安全编码
 */
export function MarkdownContent({ content }: { content: string }) {
  const html = renderMarkdown(content);
  return (
    <div
      className="markdown-content text-[15px] leading-7 md:text-base md:leading-7"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function renderMarkdown(text: string): string {
  if (!text) return "";

  let html = escapeHtml(text);

  // Code blocks (```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="my-2 rounded-lg bg-muted/70 p-3 overflow-x-auto"><code class="text-xs">${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">$1</code>');

  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4 class="font-semibold text-sm mt-3 mb-1">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="font-semibold text-base mt-4 mb-1.5">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="font-bold text-base mt-4 mb-2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="font-bold text-lg mt-4 mb-2">$1</h1>');

  // Bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong class="font-bold"><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr class="my-3 border-border" />');

  // Ordered list items
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="ml-5 list-decimal leading-7">$2</li>');

  // Unordered list items
  html = html.replace(/^[-*]\s+(.+)$/gm, '<li class="ml-5 list-disc leading-7">$1</li>');

  // Wrap consecutive <li> in <ul>/<ol>
  html = html.replace(/((?:<li class="ml-4 list-disc[^>]*>.*?<\/li>\n?)+)/g, '<ul class="my-1.5 space-y-0.5">$1</ul>');
  html = html.replace(/((?:<li class="ml-4 list-decimal[^>]*>.*?<\/li>\n?)+)/g, '<ol class="my-1.5 space-y-0.5">$1</ol>');

  // Links — with protocol whitelist (only http/https allowed)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    const safeHref = sanitizeHref(href);
    if (safeHref) {
      return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">${label}</a>`;
    }
    return label; // Strip unsafe links, render as plain text
  });

  // Footnote references [S1] [S2] etc — render as badges
  html = html.replace(/\[S(\d+)\]/g,
    '<span class="inline-flex items-center px-1 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary cursor-help" title="来源 S$1">[S$1]</span>');

  // Line breaks → paragraphs (but not inside pre/code)
  html = html
    .split("\n\n")
    .map((block) => {
      if (block.startsWith("<pre") || block.startsWith("<h") || block.startsWith("<ul") || block.startsWith("<ol") || block.startsWith("<hr")) {
        return block;
      }
      const inner = block.replace(/\n/g, "<br />");
      return `<p class="my-1">${inner}</p>`;
    })
    .join("\n");

  return html;
}

/**
 * Sanitize href — only allow http:// and https:// protocols.
 * Returns null for unsafe protocols (javascript:, data:, vbscript:, etc.)
 */
function sanitizeHref(href: string): string | null {
  // Decode HTML entities first
  const decoded = href
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .trim();

  // Only allow http/https
  if (/^https?:\/\//i.test(decoded)) {
    // Encode potentially dangerous characters in the URL
    return decoded
      .replace(/"/g, "%22")
      .replace(/'/g, "%27")
      .replace(/</g, "%3C")
      .replace(/>/g, "%3E");
  }

  // Allow relative paths (starting with /)
  if (decoded.startsWith("/")) {
    return decoded.replace(/"/g, "%22").replace(/'/g, "%27");
  }

  // Block everything else (javascript:, data:, vbscript:, etc.)
  return null;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
