import { createContext, useContext } from 'react'

// Studio context lives in its own module (not App.jsx) so that App.jsx exports
// only a component — required for React Fast Refresh to hot-update cleanly.
export const StudioContext = createContext(null)
export const useStudio = () => useContext(StudioContext)
