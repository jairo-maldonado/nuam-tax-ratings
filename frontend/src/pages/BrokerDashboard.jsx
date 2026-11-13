import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

export default function BrokerDashboard() {
    const [user, setUser] = useState(null);
    const [file, setFile] = useState(null);
    const [message, setMessage] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const [ratings, setRatings] = useState([]);
    const [auditLogs, setAuditLogs] = useState([]);
    const [filterRut, setFilterRut] = useState('');
    const [filterType, setFilterType] = useState('');

    const navigate = useNavigate();

    const fetchInitialData = async () => {
        try {
            const meRes = await api.get('auth/me/');
            setUser(meRes.data);
            await Promise.all([fetchRatings(), fetchAuditLogs()]);
        } catch (err) {
            navigate('/login');
        }
    };

    const fetchRatings = async (rut = filterRut, type = filterType) => {
        try {
            const params = {};
            if (rut) params.issuer_rut = rut;
            if (type) params.declaration_type = type;
            const res = await api.get('ratings/', { params });
            setRatings(res.data.results || []);
        } catch (err) {
            console.error(err);
        }
    };

    const fetchAuditLogs = async () => {
        try {
            const res = await api.get('audit/logs/');
            setAuditLogs(res.data.results || []);
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        fetchInitialData();
    }, []);

    const handleFileChange = (e) => {
        setFile(e.target.files[0]);
        setMessage(null);
        setError(null);
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) {
            setError("Por favor, selecciona un archivo CSV.");
            return;
        }

        setLoading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await api.post('ratings/upload/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setMessage(`¡Archivo procesado con éxito! Filas insertadas: ${response.data.created}`);
            setError(null);
            setFile(null);
            document.getElementById('csvInput').value = '';
            await Promise.all([fetchRatings(), fetchAuditLogs()]);
        } catch (err) {
            if (err.response && err.response.status === 422) {
                setError(JSON.stringify(err.response.data, null, 2));
            } else if (err.response && err.response.status === 403) {
                setError("No tienes permisos para subir archivos. Se requiere rol BROKER.");
            } else {
                setError("Ocurrió un error al procesar el archivo.");
            }
            await fetchAuditLogs();
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = (e) => {
        e.preventDefault();
        fetchRatings(filterRut, filterType);
    };

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        navigate('/login');
    };

    const isBroker = user?.role === 'BROKER';

    return (
        <div className="container mt-4 mb-5">
            <div className="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom">
                <div>
                    <h2 className="text-primary mb-0">NUAM Tax Ratings</h2>
                    {user && (
                        <span className="badge bg-secondary mt-1">
                            Usuario: {user.username} | Rol: {user.role}
                        </span>
                    )}
                </div>
                <button className="btn btn-outline-danger" onClick={handleLogout}>
                    Cerrar Sesión
                </button>
            </div>

            {/* Formulario exclusivo para BROKER */}
            {isBroker && (
                <div className="card shadow-sm p-4 mb-4">
                    <h5 className="mb-3">Carga Masiva de Calificaciones (.csv)</h5>
                    <form onSubmit={handleUpload}>
                        <div className="mb-3">
                            <input
                                type="file"
                                className="form-control"
                                id="csvInput"
                                accept=".csv"
                                onChange={handleFileChange}
                            />
                        </div>
                        <button
                            type="submit"
                            className="btn btn-success w-100 fw-bold"
                            disabled={loading}
                        >
                            {loading ? 'Procesando validaciones...' : 'Subir y Validar CSV'}
                        </button>
                    </form>

                    {message && <div className="alert alert-success mt-3 fw-bold mb-0">{message}</div>}
                    {error && (
                        <div className="alert alert-danger mt-3 mb-0">
                            <h6 className="alert-heading fw-bold">Archivo Rechazado (Error 422)</h6>
                            <pre className="mb-0" style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>{error}</pre>
                        </div>
                    )}
                </div>
            )}

            {/* Tabla de Calificaciones (PostgreSQL) - Visible para BROKER y ANALYST */}
            <div className="card shadow-sm p-4 mb-4">
                <div className="d-flex justify-content-between align-items-center mb-3">
                    <h5 className="mb-0">Calificaciones Tributarias Registradas (PostgreSQL)</h5>
                </div>

                <form className="row g-2 mb-3" onSubmit={handleSearch}>
                    <div className="col-md-5">
                        <input
                            type="text"
                            className="form-control"
                            placeholder="Filtrar por RUT (ej: 12345678-5)"
                            value={filterRut}
                            onChange={(e) => setFilterRut(e.target.value)}
                        />
                    </div>
                    <div className="col-md-4">
                        <select
                            className="form-select"
                            value={filterType}
                            onChange={(e) => setFilterType(e.target.value)}
                        >
                            <option value="">Todos los tipos (DJ_1949 / DJ_1922)</option>
                            <option value="DJ_1949">DJ_1949</option>
                            <option value="DJ_1922">DJ_1922</option>
                        </select>
                    </div>
                    <div className="col-md-3">
                        <button type="submit" className="btn btn-primary w-100">Filtrar</button>
                    </div>
                </form>

                <div className="table-responsive">
                    <table className="table table-striped table-hover align-middle mb-0">
                        <thead className="table-light">
                            <tr>
                                <th>RUT Emisor</th>
                                <th>Año Tributario</th>
                                <th>Declaración</th>
                                <th>Factor de Riesgo</th>
                                <th>Cargado por</th>
                            </tr>
                        </thead>
                        <tbody>
                            {ratings.length === 0 ? (
                                <tr>
                                    <td colSpan="5" className="text-center text-muted py-3">
                                        No hay registros que coincidan.
                                    </td>
                                </tr>
                            ) : (
                                ratings.map((r) => (
                                    <tr key={r.id}>
                                        <td className="fw-bold">{r.issuer_rut}</td>
                                        <td>{r.tax_year}</td>
                                        <td><span className="badge bg-info text-dark">{r.declaration_type}</span></td>
                                        <td>{r.risk_factor}</td>
                                        <td>{r.uploaded_by}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Historial de Auditoría (MongoDB) */}
            <div className="card shadow-sm p-4">
                <h5 className="mb-3">Registro de Auditoría de Cargas (MongoDB)</h5>
                <div className="table-responsive">
                    <table className="table table-sm table-bordered align-middle mb-0">
                        <thead className="table-light">
                            <tr>
                                <th>Fecha UTC</th>
                                <th>Usuario</th>
                                <th>Archivo</th>
                                <th>Estado</th>
                                <th>Filas Creadas / Errores</th>
                            </tr>
                        </thead>
                        <tbody>
                            {auditLogs.length === 0 ? (
                                <tr>
                                    <td colSpan="5" className="text-center text-muted py-3">
                                        Sin eventos de auditoría registrados aún.
                                    </td>
                                </tr>
                            ) : (
                                auditLogs.map((log, idx) => (
                                    <tr key={idx}>
                                        <td style={{ fontSize: '0.85rem' }}>{log.timestamp}</td>
                                        <td>{log.username}</td>
                                        <td>{log.filename || 'N/A'}</td>
                                        <td>
                                            <span className={`badge ${log.status === 'SUCCESS' ? 'bg-success' : 'bg-danger'}`}>
                                                {log.status}
                                            </span>
                                        </td>
                                        <td>
                                            {log.status === 'SUCCESS'
                                                ? `${log.created_count} insertadas`
                                                : `${log.error_count} errores`}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}