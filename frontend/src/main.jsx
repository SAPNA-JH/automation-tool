import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom'
import './index.css'
import { AuthProvider, useAuth } from './auth'
import { Loader } from './components/Loading'
import App from './App'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import Posts from './pages/Posts'
import Templates from './pages/Templates'
import FeedPreview from './pages/FeedPreview'
import Connect from './pages/Connect'
import Plan from './pages/Plan'
import Settings from './pages/Settings'

function Protected() {
  const { user, loading } = useAuth()
  if (loading)
    return (
      <div className="min-h-screen grid place-items-center">
        <Loader label="Loading your studio…" />
      </div>
    )
  if (!user) return <Landing />
  return <App />
}

function Root() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      { path: '/login', element: <Landing /> },
      {
        path: '/',
        element: <Protected />,
        children: [
          { index: true, element: <Dashboard /> },
          { path: 'posts', element: <Posts /> },
          { path: 'templates', element: <Templates /> },
          { path: 'feed', element: <FeedPreview /> },
          { path: 'connect', element: <Connect /> },
          { path: 'plan', element: <Plan /> },
          { path: 'settings', element: <Settings /> },
        ],
      },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
