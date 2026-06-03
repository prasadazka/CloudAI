import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Vi brand
        "vi-red": {
          DEFAULT: "#ED1C2E",
          dark: "#C8121F",
          light: "#FF3B4C",
        },
        "vi-yellow": {
          DEFAULT: "#FFB81C",
          dark: "#E69E00",
          light: "#FFD060",
        },
        // Semantic
        success: { DEFAULT: "#16A34A", soft: "#DCFCE7" },
        warning: { DEFAULT: "#D97706", soft: "#FEF3C7" },
        danger:  { DEFAULT: "#DC2626", soft: "#FEE2E2" },
        info:    { DEFAULT: "#2563EB", soft: "#DBEAFE" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "display": ["3rem", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "h1": ["2rem", { lineHeight: "1.2", letterSpacing: "-0.01em" }],
        "h2": ["1.5rem", { lineHeight: "1.3" }],
        "h3": ["1.25rem", { lineHeight: "1.4" }],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)",
        "card-hover": "0 8px 24px -6px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.04)",
      },
      animation: {
        "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
        "slide-in": "slideIn 0.3s ease-out",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "0.4", transform: "scale(0.85)" },
          "50%":      { opacity: "1",   transform: "scale(1)" },
        },
        slideIn: {
          "0%":   { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
