import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'

import { AppLayout } from '../layouts'

import LoginPage from '../pages/auth/LoginPage'
import DashboardPage from '../pages/dashboard/DashboardPage'
import ResourcesPage from '../pages/resources-management/ResourcesPage'
import ProductDataPage from '../pages/product-data-management/ProductDataPage'
import ProductionPage from '../pages/production/ProductionPage'
import ReportsPage from '../pages/reports/ReportsPage'
import HistoryPage from '../pages/history/HistoryPage'
import ForecastPage from '../pages/forecast/ForecastPage'

const AppRouter = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={<LoginPage />}
        />

        <Route element={<AppLayout />}>
          <Route
            path="/"
            element={
              <Navigate
                to="/dashboard"
                replace
              />
            }
          />

          <Route
            path="/dashboard"
            element={<DashboardPage />}
          />

          <Route
            path="/resources"
            element={<ResourcesPage />}
          />

          <Route
            path="/products"
            element={<ProductDataPage />}
          />

          <Route
            path="/production"
            element={<ProductionPage />}
          />

          <Route
            path="/reports"
            element={<ReportsPage />}
          />

          <Route
            path="/history"
            element={<HistoryPage />}
          />

          <Route
            path="/forecast"
            element={<ForecastPage />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter