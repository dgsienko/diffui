import { useEffect } from 'preact/hooks';

export function useAppearance({ themeCss, fontSize, wordWrap }) {
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
}
