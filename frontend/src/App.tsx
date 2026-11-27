import { Center, Loader } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router-dom'

import { isLoggedIn } from './api/auth'
import { api, type InstanceConfig } from './api/client'
import Layout from './components/Layout'
import ContainerDetail from './pages/ContainerDetail'
import Dashboard from './pages/Dashboard'
import Import from './pages/Import'
import Inventory from './pages/Inventory'
import Locations from './pages/Locations'
import Login from './pages/Login'
import NewContainer from './pages/NewContainer'

export default function App() {
  // Fetching config first also sets the CSRF cookie needed for login.
  const config = useQuery({
    queryKey: ['config'],
    queryFn: () => api<InstanceConfig>('/api/config/'),
  })
  const session = useQuery({ queryKey: ['session'], queryFn: isLoggedIn, enabled: config.isSuccess })

  if (config.isPending || (config.isSuccess && session.isPending)) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }
  if (config.isError) {
    return <Center h="100vh">Cannot reach the CheMTlab server.</Center>
  }

  const loggedIn = session.data === true
  return (
    <Routes>
      <Route
        path="/login"
        element={loggedIn ? <Navigate to="/" replace /> : <Login config={config.data} />}
      />
      <Route
        element={loggedIn ? <Layout config={config.data} /> : <Navigate to="/login" replace />}
      >
        <Route index element={<Dashboard />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="inventory/new" element={<NewContainer />} />
        <Route path="containers/:id" element={<ContainerDetail />} />
        <Route path="locations" element={<Locations />} />
        <Route path="import" element={<Import />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
