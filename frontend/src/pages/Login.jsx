import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

export default function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            // Asumiendo que tu endpoint de JWT en Django es /auth/token/
            const response = await api.post('auth/login/', { username, password });
            
            // Guardamos los tokens en el almacenamiento del navegador
            localStorage.setItem('access_token', response.data.access);
            localStorage.setItem('refresh_token', response.data.refresh);
            
            // Redirigimos al dashboard tras el inicio de sesión exitoso
            navigate('/dashboard');
        } catch (err) {
            setError('Credenciales inválidas. Verifica tu usuario y contraseña.');
        }
    };

    return (
        <div className="container d-flex justify-content-center align-items-center vh-100">
            <div className="card shadow p-4" style={{ width: '100%', maxWidth: '400px' }}>
                <h2 className="text-center mb-4 text-primary">NUAM Tax Ratings</h2>
                {error && <div className="alert alert-danger">{error}</div>}
                <form onSubmit={handleSubmit}>
                    <div className="mb-3">
                        <label className="form-label">Usuario</label>
                        <input 
                            type="text" 
                            className="form-control" 
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required 
                        />
                    </div>
                    <div className="mb-3">
                        <label className="form-label">Contraseña</label>
                        <input 
                            type="password" 
                            className="form-control" 
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required 
                        />
                    </div>
                    <button type="submit" className="btn btn-primary w-100 fw-bold">Iniciar Sesión</button>
                </form>
            </div>
        </div>
    );
}