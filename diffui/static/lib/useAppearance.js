import { useEffect } from 'preact/hooks';

export const WORD_HIGHLIGHT_STYLES = ['background', 'underline', 'off'];

export function useAppearance({ themeCss, fontSize, wordWrap, wordHighlight }) {
  useEffect(() => {
    if (themeCss) {
      let style = document.getElementById('theme-vars');
      if (!style) {
        style = document.createElement('style');
        style.id = 'theme-vars';
        document.head.appendChild(style);
      }
      style.textContent = themeCss;
    }
  }, [themeCss]);

  useEffect(() => {
    document.documentElement.style.setProperty('--code-font-size', `${fontSize}px`);
  }, [fontSize]);

  useEffect(() => {
    document.documentElement.classList.toggle('word-wrap-enabled', wordWrap);
  }, [wordWrap]);

  useEffect(() => {
    const root = document.documentElement.classList;
    for (const style of WORD_HIGHLIGHT_STYLES) root.toggle(`word-hl-${style}`, style === wordHighlight);
  }, [wordHighlight]);
}
