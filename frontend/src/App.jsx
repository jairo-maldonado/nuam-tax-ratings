import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import BrokerDashboard from './pages/BrokerDashboard';

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Navigate to="/login" />} />
                <Route path="/login" element={<Login />} />
                {/* Ahora el dashboard apunta a nuestro componente real */}
                <Route path="/dashboard" element={<BrokerDashboard />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;