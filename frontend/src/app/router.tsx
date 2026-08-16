import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'

import { AppLayout } from '../layouts'

import GuestRoute from '../auth/GuestRoute'
import ProtectedRoute from '../auth/ProtectedRoute'

import LoginPage from '../pages/auth/LoginPage'
import DashboardPage from '../pages/dashboard/DashboardPage'
import ResourcesPage from '../pages/resources-management/ResourcesPage'
import ProductDataPage from '../pages/product-data-management/ProductDataPage'
import ProductionPage from '../pages/production-allocation/ProductionAllocationPage'
import ReportsPage from '../pages/resource-utilization-report/ResourceUtilizationReportPage'
import HistoryPage from '../pages/transaction-history/TransactionHistoryPage'
import OptimizationHistoryPage from '../pages/optimization-history/OptimizationHistoryPage'
import DemandForecastingPage from '../pages/demand-forecasting/DemandForecastingPage'

const AppRouter = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<GuestRoute />}>
          <Route
            path="/login"
            element={<LoginPage />}
          />
        </Route>

        <Route element={<ProtectedRoute />}>
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
              path="/optimization-history"
              element={<OptimizationHistoryPage />}
            />

            <Route
              path="/demand-forecasting"
              element={<DemandForecastingPage />}
            />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter