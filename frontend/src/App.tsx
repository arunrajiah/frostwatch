import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Queries from './pages/Queries';
import Warehouses from './pages/Warehouses';
import Anomalies from './pages/Anomalies';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import Dbt from './pages/Dbt';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/queries" element={<Queries />} />
        <Route path="/warehouses" element={<Warehouses />} />
        <Route path="/dbt" element={<Dbt />} />
        <Route path="/anomalies" element={<Anomalies />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
