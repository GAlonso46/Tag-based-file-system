import { useState, useEffect } from 'react';
import { fetchStats, fetchPopularTags } from '../services/api';

export const useStats = () => {
    const [stats, setStats] = useState({ total_files: 0, total_size: 0, total_tags: 0 });
    const [popularTags, setPopularTags] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStats();
        loadPopularTags();
    }, []);

    const loadStats = async () => {
        try {
            const data = await fetchStats();
            console.log('📊 Stats recibidas del API:', data); // Debug
            
            // Normalizar los datos (el API devuelve total_size_bytes)
            const normalizedStats = {
                total_files: data.total_files || 0,
                total_size: data.total_size_bytes || data.total_size || 0,
                total_tags: data.total_tags || 0
            };
            
            setStats(normalizedStats);
        } catch (err) {
            console.error('❌ Error loading stats:', err);
        }
    };

    const loadPopularTags = async () => {
        try {
            const data = await fetchPopularTags();
            console.log('🏷️ Tags recibidos del API:', data); // Debug
            
            // API devuelve {tags: [{name, count}], total: N}
            const tagsArray = data.tags || data || [];
            
            // Normalizar: convertir [{name, count}] a [[name, count]]
            const normalizedTags = Array.isArray(tagsArray) 
                ? tagsArray.map(tag => [tag.name, tag.count])
                : [];
            
            console.log('✅ Tags normalizados:', normalizedTags); // Debug
            setPopularTags(normalizedTags);
        } catch (err) {
            console.error('❌ Error loading tags:', err);
            setPopularTags([]);
        } finally {
            setLoading(false);
        }
    };

    const refresh = () => {
        loadStats();
        loadPopularTags();
    };

    return { stats, popularTags, loading, refresh };
};
