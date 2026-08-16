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
import RegisterPage from '../pages/auth/RegisterPage'
import ForgotPasswordPage from '../pages/auth/ForgotPasswordPage'
import ResetPasswordPage from '../pages/auth/ResetPasswordPage'
import DashboardPage from '../pages/dashboard/DashboardPage'
import ResourcesPage from '../pages/resources-management/ResourcesPage'
import ProductDataPage from '../pages/product-data-management/ProductDataPage'
import ProductionPage from '../pages/production-allocation/ProductionAllocationPage'
import ReportsPage from '../pages/resource-utilization-report/ResourceUtilizationReportPage'
import ResourceUtilizationHistoryPage from '../pages/resource-utilization-history/ResourceUtilizationHistoryPage'
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

          <Route
            path="/register"
            element={<RegisterPage />}
          />

          <Route
            path="/forgot-password"
            element={<ForgotPasswordPage />}
          />

          <Route
            path="/reset-password"
            element={<ResetPasswordPage />}
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
              path="/resource-utilization-history"
              element={<ResourceUtilizationHistoryPage />}
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