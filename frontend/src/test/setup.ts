import '@testing-library/jest-dom/vitest'

// jsdom does not implement window.matchMedia - Mantine's
// MantineProvider (color scheme detection) and other components call
// it on mount/effect. Without this, any test that renders a Mantine
// tree throws "window.matchMedia is not a function".
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as unknown as MediaQueryList
}

// jsdom also does not implement ResizeObserver, which Mantine's
// ScrollArea (used inside Select/combobox dropdowns, etc.) observes
// on mount.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  globalThis.ResizeObserver =
    ResizeObserverStub as unknown as typeof ResizeObserver
}

// jsdom does not implement the CSS Font Loading API either. Mantine's
// autosize Textarea subscribes to document.fonts "loadingdone" to
// remeasure rows, so rendering one throws without this stub.
if (typeof document !== 'undefined' && !document.fonts) {
  Object.defineProperty(document, 'fonts', {
    configurable: true,
    value: {
      addEventListener: () => {},
      removeEventListener: () => {},
    },
  })
}
