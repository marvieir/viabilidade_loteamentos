// Revalidação ISR on-demand (porta do desenho do MMA/voya): o gerador de blog (BLOG-2)
// grava o artigo e chama POST /webhooks/revalidate?path=/blog/<slug>&secret=... para
// publicar SEM rebuild. Sem REVALIDATE_SECRET configurado no ambiente, o endpoint fica
// desligado (401 sempre) — seguro por padrão.

import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const esperado = process.env.REVALIDATE_SECRET;
  const secret = req.nextUrl.searchParams.get("secret");
  if (!esperado || secret !== esperado) {
    return NextResponse.json({ erro: "não autorizado" }, { status: 401 });
  }
  const path = req.nextUrl.searchParams.get("path");
  if (!path || !path.startsWith("/")) {
    return NextResponse.json({ erro: "path inválido" }, { status: 400 });
  }
  revalidatePath(path);
  return NextResponse.json({ revalidado: path });
}
