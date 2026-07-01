"use client";

import Link from "next/link";
import { IconDownload, IconMap, IconPlay, IconPlus, IconChevron } from "@/components/Icons";
import { Button } from "@/components/ui/button";
import { Menu, MenuDivisor, MenuItem, MenuLabel } from "@/components/ui/menu";
import { useAuth } from "@/components/auth/AuthProvider";
import type { Analise } from "@/lib/api";

const ROTULO_COBERTURA: Record<string, string> = {
  BASE_FEDERAL: "Base Federal",
  PARCIAL_UF: "Parcial (UF)",
  COMPLETA: "Completa",
};

export function TopBar({
  analise,
  onNova,
  onAnalisarTudo,
  analisando,
  onLaudo,
  gerandoLaudo,
  onExcel,
  gerandoExcel,
  onSalvar,
  salvando,
  jaSalva,
}: {
  analise: Analise | null;
  onNova: () => void;
  onAnalisarTudo: () => void;
  analisando?: boolean;
  onLaudo?: () => void;
  gerandoLaudo?: boolean;
  onExcel?: () => void;
  gerandoExcel?: boolean;
  onSalvar?: () => void;
  salvando?: boolean;
  jaSalva?: boolean;
}) {
  const { usuario, sair } = useAuth();
  const jur = analise?.jurisdicao;
  const local =
    jur?.municipio && jur?.uf
      ? `${jur.municipio} / ${jur.uf}`
      : jur?.uf || "Jurisdição federal";
  const exportando = gerandoLaudo || gerandoExcel;
  const iniciais = (usuario?.nome || usuario?.email || "?")
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");

  return (
    <header className="sticky top-0 z-[1100] flex h-14 items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-5">
      {/* Marca */}
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
          <IconMap width={17} height={17} />
        </div>
        <p className="truncate text-sm font-bold tracking-tight">
          Pré-Viabilidade <span className="hidden font-medium text-slate-400 md:inline">· Loteamento</span>
        </p>
        {/* Contexto da análise (gleba atual) */}
        {analise && (
          <div className="ml-1 hidden min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 lg:flex">
            <span className="truncate text-xs font-semibold text-slate-700">{local}</span>
            <span className="h-3 w-px shrink-0 bg-slate-300" />
            <span className="shrink-0 text-xs text-slate-500">
              {analise.geometria.area_ha.toLocaleString("pt-BR")} ha
            </span>
            <span className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">
              {ROTULO_COBERTURA[analise.jurisdicao.cobertura] ?? "—"}
            </span>
          </div>
        )}
      </div>

      {/* Toolbar — botões uniformes (design system); ações de exportação agrupadas */}
      <div className="flex shrink-0 items-center gap-2">
        {analise && (
          <>
            <Button variant="secondary" onClick={onAnalisarTudo} disabled={analisando}>
              <IconPlay width={14} height={14} />
              <span className="hidden sm:inline">{analisando ? "Analisando…" : "Analisar tudo"}</span>
            </Button>
            {onSalvar && (
              <Button
                variant="secondary"
                onClick={onSalvar}
                disabled={salvando}
                title="Salva esta análise em 'Minhas análises' (geometria + resultados)"
              >
                {salvando ? "Salvando…" : jaSalva ? "Atualizar" : "Salvar"}
              </Button>
            )}
            {(onLaudo || onExcel) && (
              <Menu
                botao={
                  <Button variant="secondary" disabled={exportando}>
                    <IconDownload width={14} height={14} />
                    <span className="hidden sm:inline">
                      {exportando ? "Gerando…" : "Exportar"}
                    </span>
                    <IconChevron width={12} height={12} className="opacity-50" />
                  </Button>
                }
              >
                {onLaudo && (
                  <MenuItem onClick={onLaudo} disabled={gerandoLaudo}>
                    <IconDownload width={14} height={14} className="text-slate-400" />
                    Laudo de triagem (PDF)
                  </MenuItem>
                )}
                {onExcel && (
                  <MenuItem onClick={onExcel} disabled={gerandoExcel}>
                    <IconDownload width={14} height={14} className="text-slate-400" />
                    Planilha (Excel)
                  </MenuItem>
                )}
              </Menu>
            )}
          </>
        )}
        <Button onClick={onNova}>
          <IconPlus width={14} height={14} />
          <span className="hidden sm:inline">Nova análise</span>
        </Button>

        {/* Menu do usuário (avatar) — e-mail/admin/sair saem da barra, entram no menu */}
        {usuario && (
          <Menu
            botao={
              <button
                type="button"
                title={usuario.email}
                className="ml-1 grid h-9 w-9 place-items-center rounded-full border border-slate-200 bg-slate-100 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-200"
              >
                {iniciais || "?"}
              </button>
            }
          >
            <MenuLabel>{usuario.email}</MenuLabel>
            {usuario.papel === "admin" && (
              <Link href="/admin" className="block">
                <MenuItem>Painel do administrador</MenuItem>
              </Link>
            )}
            <MenuDivisor />
            <MenuItem onClick={sair} destaque>
              Sair
            </MenuItem>
          </Menu>
        )}
      </div>
    </header>
  );
}
