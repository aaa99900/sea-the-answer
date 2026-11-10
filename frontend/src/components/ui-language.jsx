"use client";
import React, {createContext, useContext} from 'react';
import {translateUi} from '../lib/ui-language';
export const UiLanguageContext = createContext('ko');
export function UiText({children}) {
  const language = useContext(UiLanguageContext);
  return React.Children.map(children, value => typeof value === 'string' ? translateUi(value, language) : value);
}
// Only UI attributes are translated. Input values and all data attributes remain intact.
export function UiControl({as: Tag, children, ...props}) {
  const language = useContext(UiLanguageContext);
  for (const key of ['placeholder', 'aria-label', 'title']) {
    if (typeof props[key] === 'string') props[key] = translateUi(props[key], language);
  }
  return <Tag {...props}>{children}</Tag>;
}
