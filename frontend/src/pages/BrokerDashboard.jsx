import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

export default function BrokerDashboard() {
    const [file, setFile] = useState(null);
    const [message, setMessage] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

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
            // Ajustaremos esta URL si tu backend usa otra distinta
            const response = await api.post('ratings/upload/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setMessage("¡Archivo procesado con éxito! Todas las reglas de negocio se cumplieron.");
            setFile(null); // Limpiamos el input
            document.getElementById('csvInput').value = '';
        } catch (err) {
            if (err.response && err.response.status === 422) {
                // Error de reglas de negocio (ej: suma > 1.0000)
                setError(JSON.stringify(err.response.data, null, 2));
            } else if (err.response && err.response.status === 403) {
                setError("No tienes permisos para subir archivos. ¿Iniciaste sesión como Broker?");
            } else {
                setError("Ocurrió un error al procesar el archivo.");
            }
        } finally {
            setLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        navigate('/login');
    };

    return (
        <div className="container mt-5">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary">Panel de Broker - Subida de CSV</h2>
                <button className="btn btn-outline-danger" onClick={handleLogout}>Cerrar Sesión</button>
            </div>

            <div className="card shadow p-4">
                <form onSubmit={handleUpload}>
                    <div className="mb-3">
                        <label className="form-label fw-bold">Selecciona el archivo de Tax Ratings (.csv)</label>
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
            </div>

            {/* Mensajes de éxito o error */}
            {message && <div className="alert alert-success mt-4 fw-bold">{message}</div>}
            {error && (
                <div className="alert alert-danger mt-4">
                    <h5 className="alert-heading">Archivo Rechazado (Error 422)</h5>
                    <pre style={{ whiteSpace: 'pre-wrap' }}>{error}</pre>
                </div>
            )}
        </div>
    );
}