import type { Config } from "tailwindcss";

// Identidade voaz.app (aprovada pelo operador em 29/07 — direção A dominante, toque
// editorial da B reservado ao laudo e às capas de marketing).
//
// REGRA DE USO — quebrar isto descaracteriza a marca:
//   · laranja = ÚNICO acento decorativo (botão primário, link, foco, destaque)
//   · verde   = SIGNIFICADO, nunca enfeite (conforme, confirmado, dentro da faixa)
//   · marinho = fundo dominante das superfícies de trabalho
//   · creme   = superfície de leitura (conteúdo, cards, tabelas)
// Num produto que emite laudo o usuário precisa aprender que verde na tela QUER DIZER algo;
// se verde também for decoração, ele para de confiar no verde.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        marinho: {
          DEFAULT: "#170d48",
          50: "#f3f1fb",
          100: "#e8e2ff",
          200: "#c3b8e8",
          300: "#9287c4",
          400: "#7b719e",
          500: "#4a3f7a",
          600: "#2e1f7a",
          700: "#241862",
          800: "#1d1252",
          900: "#170d48",
          950: "#100a33",
        },
        laranja: {
          DEFAULT: "#ff914d",
          50: "#fff4ec",
          100: "#ffe4d1",
          200: "#ffc9a5",
          300: "#ffad78",
          400: "#ff914d",
          500: "#f07d33",
          600: "#db6b1a",
          700: "#b45613",
          800: "#8c4210",
          900: "#632f0c",
        },
        creme: {
          DEFAULT: "#fff4f4",
          50: "#fffafa",
          100: "#fff4f4",
          200: "#fdeae4",
          300: "#f3e9e0",
          400: "#e3d5c8",
        },
        // Semânticos — SÓ para estado (ver regra acima).
        verde: {
          DEFAULT: "#3a806f",
          claro: "#a2dfbb",
          escuro: "#2c6154",
        },
        // Papel: superfície editorial do laudo e das capas (direção B, uso pontual).
        papel: {
          DEFAULT: "#fbf6f1",
          escuro: "#f3e9e0",
          linha: "#e3d5c8",
          tinta: "#1b120c",
          tinta2: "#5b4a3e",
          tinta3: "#96796a",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI",
               "Roboto", "sans-serif"],
        serifa: ["Fraunces", "Georgia", "Iowan Old Style", "Times New Roman", "serif"],
        // Todo NÚMERO sai em monoespaçada: a promessa é número com procedência, então o
        // dígito ganha tratamento de dado — e as colunas de área alinham à vista.
        mono: ["ui-monospace", "SF Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
