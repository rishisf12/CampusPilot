/**
 * Sanitize HTML for safe display in reading pane.
 * In production this runs server-side via nh3; here we do a basic client-side strip
 * of script/event-handler attributes as a defense-in-depth measure.
 */
export function sanitizeHtml(html: string): string {
  if (!html) return ""
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
    .replace(/on\w+="[^"]*"/g, "")
    .replace(/on\w+='[^']*'/g, "")
    .replace(/javascript:/gi, "")
    .replace(/<iframe\b[^>]*>/gi, "")
    .replace(/<\/iframe>/gi, "")
}
