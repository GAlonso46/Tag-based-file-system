import { API_URL } from '../config';

// Función para obtener headers con autenticación
const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    const headers = {
        'Content-Type': 'application/json'
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    return headers;
};

// Obtener todos los archivos o filtrar por tags
export const fetchFiles = async (tags = null) => {
    const url = tags ? `${API_URL}/files?tags=${tags}` : `${API_URL}/files`;
    const response = await fetch(url, {
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Error al cargar archivos');
    return response.json();
};

// Subir archivo
export const uploadFile = async (file, tags) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tags', tags.join(','));

    const token = localStorage.getItem('token');
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_URL}/files`, {
        method: 'POST',
        headers: headers,
        body: formData
    });

    if (!response.ok) throw new Error('Error al subir archivo');
    return response.json();
};

// Actualizar tags de un archivo
export const updateFileTags = async (filename, tags) => {
    console.log('🔄 API: Actualizando tags para:', filename, 'Tags:', tags); // Debug
    
    if (!filename) {
        console.error('❌ API: filename es undefined o vacío');
        throw new Error('Filename es requerido');
    }
    
    const response = await fetch(`${API_URL}/files/${filename}/tags`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ tags })
    });

    if (!response.ok) throw new Error('Error al actualizar tags');
    return response.json();
};

// Eliminar archivo
export const deleteFile = async (filename) => {
    const token = localStorage.getItem('token');
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_URL}/files/${filename}`, {
        method: 'DELETE',
        headers: headers
    });

    if (!response.ok) throw new Error('Error al eliminar archivo');
    return response.json();
};

// Descargar archivo
export const downloadFile = async (file) => {
    try {
        // Usar file_id si está disponible, sino usar filename
        const fileId = file.id || file.file_id || file.name || file.filename;
        const filename = file.name || file.filename || 'download';
        
        const response = await fetch(`${API_URL}/files/${fileId}`, {
            headers: getAuthHeaders()
        });
        
        if (!response.ok) {
            throw new Error('Error al descargar archivo');
        }
        
        // Obtener el blob del archivo
        const blob = await response.blob();
        
        // Crear un enlace temporal para descargar
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        // Limpiar
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Error al descargar archivo:', error);
        alert('Error al descargar el archivo');
    }
};

// Obtener estadísticas
export const fetchStats = async () => {
    const response = await fetch(`${API_URL}/stats`, {
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Error al cargar estadísticas');
    return response.json();
};

// Obtener tags populares
export const fetchPopularTags = async () => {
    const response = await fetch(`${API_URL}/tags`, {
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Error al cargar tags');
    return response.json();
};
