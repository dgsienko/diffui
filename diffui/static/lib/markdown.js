import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

export function renderMd(text) {
  return { __html: marked.parse(text || '') };
}
