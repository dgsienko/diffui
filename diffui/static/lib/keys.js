// Default key for each rebindable action. A key saved in settings.keybindings wins.
export const DEFAULT_KEYS = {
  'toggle-review': 'r',
  'toggle-show-reviewed': 'a',
  'comment-line': 'c',
  'copy-path': 'y',
  'sort-risk': 's',
  'export-summary': 'S',
  'toggle-file-tree': 'b',
  'next-unreviewed': ']',
};

export function kb(keybindings, id) {
  return keybindings?.[id] || DEFAULT_KEYS[id];
}
