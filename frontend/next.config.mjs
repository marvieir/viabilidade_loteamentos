/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Empacota um servidor mínimo (só o node_modules rastreado) em .next/standalone.
  // Evita copiar o node_modules inteiro pra imagem — muito menor, não estoura disco.
  output: "standalone",
};

export default nextConfig;
