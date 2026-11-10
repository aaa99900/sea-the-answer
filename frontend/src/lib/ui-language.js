import messages from './ui-messages.json';
export const UI_LANGUAGE_KEY = 'haedap-ui-language';
export function translateUi(text, language) {
  if (language !== 'en' || typeof text !== 'string') return text;
  const key = text.trim();
  const translated = Object.hasOwn(messages, key) ? messages[key] : undefined;
  return translated === undefined ? text : text.replace(key, () => translated);
}
