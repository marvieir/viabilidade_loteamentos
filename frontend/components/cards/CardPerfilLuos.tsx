"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  confirmarPerfil,
  extrairPerfil,
  obterPerfil,
  type ParamProv,
  type PerfilMunicipal,
  type ZonaPerfil,
} from "@/lib/api";

// Parâmetros que ENTRAM no número (gateados): exigem citação para confirmar (decisão §6-B).
const GATEADOS: { chave: "lote_min_m2" | "doacao_pct"; rotulo: string; frac?: boolean }[] = [
  { chave: "lote_min_m2", rotulo: "Lote mínimo (m²)" },
  { chave: "doacao_pct", rotulo: "Doação (fração, ex. 0.35)", frac: true },
];

export function CardPerfilLuos({
  codIbge,
  municipio,
  uf,
  onConfirmado,
}: {
  codIbge: string | null;
  municipio: string | null;
  uf: string | null;
  onConfirmado: (perfil: PerfilMunicipal | null) => void;
}) {
  const [perfil, setPerfil] = useState<PerfilMunicipal | null>(null);
  const [validadoPor, setValidadoPor] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  // Recarrega o perfil confirmado existente (sem re-extrair) quando o município muda.
  useEffect(() => {
    setPerfil(null);
    setErro(null);
    if (!codIbge) return;
    obterPerfil(codIbge)
      .then((p) => {
        if (p) {
          setPerfil(p);
          setValidadoPor(p.validado_por ?? "");
          onConfirmado(p);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codIbge]);

  if (!codIbge) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Diretriz municipal (LUOS)</CardTitle>
          <CardDescription>
            Resolva o município (acima) para extrair a LUOS e reintroduzir doação e lote
            legal no número.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  async function enviarPdf(file: File) {
    setCarregando(true);
    setErro(null);
    try {
      const p = await extrairPerfil(codIbge!, file, municipio, uf);
      setPerfil(p);
      onConfirmado(null); // novo rascunho → invalida o cenário até confirmar
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha na extração.");
    } finally {
      setCarregando(false);
    }
  }

  function editarParam(
    zonaIdx: number,
    chave: "lote_min_m2" | "doacao_pct",
    campo: keyof ParamProv,
    valor: string
  ) {
    setPerfil((prev) => {
      if (!prev) return prev;
      const zonas = prev.zonas.map((z, i) => {
        if (i !== zonaIdx) return z;
        const atual = z.params[chave];
        const base: ParamProv =
          atual ?? {
            valor: null,
            artigo: null,
            pagina: null,
            trecho: null,
            origem: "editado_humano",
          };
        const novo: ParamProv = {
          ...base,
          origem: "editado_humano",
          [campo]:
            campo === "valor" || campo === "pagina"
              ? valor === ""
                ? null
                : Number(valor)
              : valor === ""
                ? null
                : valor,
        };
        return { ...z, params: { ...z.params, [chave]: novo } };
      });
      return { ...prev, status: "proposto", zonas };
    });
  }

  async function confirmar() {
    if (!perfil) return;
    setCarregando(true);
    setErro(null);
    try {
      const p = await confirmarPerfil(codIbge!, perfil, validadoPor || "—");
      setPerfil(p);
      onConfirmado(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao confirmar.");
    } finally {
      setCarregando(false);
    }
  }

  const confirmado = perfil?.status === "confirmado";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Diretriz municipal (LUOS)</span>
          {confirmado ? (
            <StatusChip className="ml-auto" estado="ok" rotulo="confirmada" />
          ) : perfil ? (
            <StatusChip className="ml-auto" estado="atencao" rotulo="aguarda confirmação" />
          ) : (
            <StatusChip className="ml-auto" estado="pendente" />
          )}
        </CardTitle>
        <CardDescription>
          O assistente <strong>lê o PDF e propõe</strong> os índices por zona, cada um com a
          citação ao lado. Nada entra no cálculo sem a sua confirmação. Determinismo e
          proveniência preservados — a IA fica na leitura, nunca no número.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-medium text-slate-700">
            PDF da LUOS / lei de parcelamento
            <input
              type="file"
              accept="application/pdf"
              disabled={carregando}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) enviarPdf(f);
              }}
              className="mt-1 block text-xs text-slate-600 file:mr-2 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-3 file:py-1.5 file:text-xs"
            />
          </label>
          {carregando && <span className="text-xs text-slate-500">processando…</span>}
        </div>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {perfil && (
          <>
            <div
              className={`flex items-center gap-2 text-xs ${
                confirmado ? "text-emerald-700" : "text-amber-700"
              }`}
            >
              <span
                className={`rounded-full px-2 py-0.5 font-medium ${
                  confirmado ? "bg-emerald-100" : "bg-amber-100"
                }`}
              >
                {confirmado ? "perfil confirmado" : "rascunho — proposto (não calcula)"}
              </span>
              {perfil.fonte_documento && <span>fonte: {perfil.fonte_documento}</span>}
              {confirmado && perfil.data_referencia && (
                <span>· validado por {perfil.validado_por} em {perfil.data_referencia}</span>
              )}
            </div>

            {perfil.avisos.length > 0 && (
              <div className="rounded-lg bg-sky-50 p-3 text-xs text-sky-900">
                {perfil.avisos.map((a) => (
                  <p key={a}>{a}</p>
                ))}
              </div>
            )}

            <div className="space-y-3">
              {perfil.zonas.map((z, i) => (
                <ZonaEditor
                  key={z.codigo}
                  zona={z}
                  somenteLeitura={confirmado}
                  onEditar={(chave, campo, valor) => editarParam(i, chave, campo, valor)}
                />
              ))}
            </div>

            {!confirmado && (
              <div className="flex flex-wrap items-end gap-3 border-t border-slate-200 pt-3">
                <label className="flex flex-col gap-1 text-xs text-slate-600">
                  Validado por (seu nome)
                  <input
                    value={validadoPor}
                    onChange={(e) => setValidadoPor(e.target.value)}
                    placeholder="Eng. responsável"
                    className="rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900"
                  />
                </label>
                <Button onClick={confirmar} disabled={carregando}>
                  Confirmar perfil (entra no cálculo)
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ZonaEditor({
  zona,
  somenteLeitura,
  onEditar,
}: {
  zona: ZonaPerfil;
  somenteLeitura: boolean;
  onEditar: (
    chave: "lote_min_m2" | "doacao_pct",
    campo: keyof ParamProv,
    valor: string
  ) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-semibold text-slate-900">
        {zona.codigo}
        {zona.descricao ? (
          <span className="ml-2 font-normal text-slate-500">{zona.descricao}</span>
        ) : null}
      </p>
      <div className="mt-2 space-y-2">
        {GATEADOS.map(({ chave, rotulo }) => {
          const p = zona.params[chave];
          return (
            <div
              key={chave}
              className="grid grid-cols-1 gap-2 rounded-md bg-slate-50 p-2 sm:grid-cols-[1fr,2fr]"
            >
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                {rotulo}
                <input
                  type="number"
                  step="any"
                  disabled={somenteLeitura}
                  value={p?.valor ?? ""}
                  placeholder="não encontrado"
                  onChange={(e) => onEditar(chave, "valor", e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm text-slate-900 disabled:bg-slate-100"
                />
              </label>
              <div className="flex flex-col gap-1 text-xs text-slate-600">
                <div className="flex gap-1">
                  <input
                    disabled={somenteLeitura}
                    value={p?.artigo ?? ""}
                    placeholder="Art. (citação obrigatória)"
                    onChange={(e) => onEditar(chave, "artigo", e.target.value)}
                    className="w-2/3 rounded border border-slate-300 px-2 py-1 text-xs text-slate-900 disabled:bg-slate-100"
                  />
                  <input
                    type="number"
                    disabled={somenteLeitura}
                    value={p?.pagina ?? ""}
                    placeholder="pág."
                    onChange={(e) => onEditar(chave, "pagina", e.target.value)}
                    className="w-1/3 rounded border border-slate-300 px-2 py-1 text-xs text-slate-900 disabled:bg-slate-100"
                  />
                </div>
                {p?.trecho && (
                  <span className="italic text-slate-500">“{p.trecho}”</span>
                )}
                {p && (
                  <span className="text-[10px] uppercase tracking-wide text-slate-400">
                    {p.origem === "editado_humano" ? "editado" : "proposto pelo LLM"}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
