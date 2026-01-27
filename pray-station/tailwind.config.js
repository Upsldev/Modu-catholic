/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                "altar-parchment": "#f4f1e8",
                "altar-sage": "#6b705c",
                "altar-olive": "#a5a58d",
                "altar-earth": "#4b483f",
                "altar-gold": "#c5a059",
                "wood-light": "#fdfbf7",
                "wood-shade": "#efeadd",
                "wood-dark": "#d4cec3",
            },
            fontFamily: {
                "display": ["Manrope", "sans-serif"]
            },
            boxShadow: {
                'bead-raised': '4px 4px 10px rgba(0,0,0,0.1), -2px -2px 6px rgba(255,255,255,0.8)',
                'bead-inset': 'inset 4px 4px 8px rgba(0,0,0,0.05), inset -2px -2px 6px rgba(255,255,255,0.6)',
                'altar-frame': '0 0 0 16px #e2ddd0, 0 30px 60px rgba(0,0,0,0.15)',
            },
            animation: {
                'slide-up': 'slideUp 0.4s ease-out',
                'fade-in': 'fadeIn 0.3s ease-out',
            },
            keyframes: {
                slideUp: {
                    '0%': { transform: 'translateY(100%)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
            },
        },
    },
    plugins: [],
}
