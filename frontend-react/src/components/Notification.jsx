import { useNotification } from '../context/NotificationContext';
import './Notification.css';

export const Notification = () => {
    const { notification } = useNotification();

    if (!notification) return null;

    return (
        <div className={`notification ${notification.type} active`}>
            <span className="notification-icon">
                {notification.type === 'success' ? '✅' : '❌'}
            </span>
            <span className="notification-message">{notification.message}</span>
        </div>
    );
};
