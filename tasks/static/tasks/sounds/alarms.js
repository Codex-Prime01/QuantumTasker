// Default alarm tones (embedded as data URLs so no file uploads needed!)
const DEFAULT_ALARM_TONES = {
    'gentle': {
        name: '🔔 Gentle Bell',
        url: 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='
    },
    'classic': {
        name: '⏰ Classic Alarm',
        description: 'Traditional beep beep beep',
        duration: 3
    },
    'chime': {
        name: '🎵 Soft Chime',
        description: 'Pleasant notification sound',
        duration: 2
    },
    'urgent': {
        name: '🚨 Urgent Alert',
        description: 'Loud and attention-grabbing',
        duration: 5
    }
};
