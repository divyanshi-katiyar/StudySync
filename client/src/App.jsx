import { Navigate, Route, Routes } from 'react-router-dom'
import PublicLayout from './components/layout/PublicLayout'
import AppLayout from './components/layout/AppLayout'
import ProtectedRoute from './components/layout/ProtectedRoute'
import Landing from './pages/Landing'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import MyGroups from './pages/MyGroups'
import Discover from './pages/Discover'
import GroupDetail from './pages/GroupDetail'
import PostDetail from './pages/PostDetail'
import SessionsPage from './pages/SessionsPage'
import Profile from './pages/Profile'
import NotFound from './pages/NotFound'

/**
 * Route map (matches the Week 1 flowcharts):
 *   /                      landing page (public)
 *   /login, /register      authentication (public)
 *   /app/dashboard         personal dashboard
 *   /app/groups            groups I belong to
 *   /app/discover          search public groups
 *   /app/groups/:id        group workspace (tabs: resources, discussion, sessions, members)
 *   /app/groups/:id/posts/:postId   discussion thread
 *   /app/sessions          upcoming sessions across all groups
 *   /app/profile           account settings
 */
export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="login" element={<AuthPage mode="login" />} />
        <Route path="register" element={<AuthPage mode="register" />} />
      </Route>

      <Route path="app" element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="groups" element={<MyGroups />} />
          <Route path="discover" element={<Discover />} />
          <Route path="groups/:groupId" element={<GroupDetail />} />
          <Route path="groups/:groupId/posts/:postId" element={<PostDetail />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="profile" element={<Profile />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
